import SwiftUI
import Combine

struct AIChatView: View {
    @EnvironmentObject var appState: AppState

    @State private var messages: [AIConversationMessage] = [AIChatView.introMessage]
    @State private var entries: [AIChatLogItem] = [.message(AIChatView.introMessage)]
    @State private var input = ""
    @State private var ideaContext = ""
    @State private var busyState: AIChatBusyState? = nil

    private static let introMessage = AIConversationMessage(
        role: .assistant,
        text: "I'm your FollowThru habit coach. Tell me what kind of change you want in your life, what you're struggling with, and anything that would make the habit realistic or unrealistic for you."
    )

    private var isBusy: Bool { busyState != nil }

    private var hasSuccessEntry: Bool {
        entries.contains { entry in
            if case .success = entry.content {
                return true
            }
            return false
        }
    }

    private var activeProposalEntryID: UUID? {
        entries.last(where: { entry in
            guard case .proposals(let block) = entry.content else { return false }
            return block.state == .active
        })?.id
    }

    private var showsComposer: Bool {
        !isBusy && !hasSuccessEntry
    }

    private var composerPlaceholder: String {
        activeProposalEntryID != nil
            ? "Ask to adjust, change schedule, swap a day..."
            : "Tell me what kind of change you want to make..."
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 14) {
                            ForEach(entries) { entry in
                                entryView(entry)
                                    .id(entry.id)
                            }

                            Color.clear
                                .frame(height: 1)
                                .id("bottom")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }
                    .onChange(of: entries.count, initial: false) { _, _ in
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo("bottom", anchor: .bottom)
                        }
                    }
                    .onAppear {
                        proxy.scrollTo("bottom", anchor: .bottom)
                    }
                }

                if showsComposer {
                    composerBar
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Habit Coach")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var composerBar: some View {
        VStack(spacing: 0) {
            Divider().background(Theme.border)
            HStack(alignment: .bottom, spacing: 10) {
                ZStack(alignment: .leading) {
                    if input.isEmpty {
                        AnimatedComposerPlaceholder(text: composerPlaceholder)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                    }

                    TextField("", text: $input, axis: .vertical)
                        .lineLimit(1...4)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                }
                .background(Theme.white)
                .cornerRadius(14)
                .overlay(
                    RoundedRectangle(cornerRadius: 14)
                        .stroke(Theme.border, lineWidth: 1)
                )

                Button(action: sendMessage) {
                    Image(systemName: isBusy ? "hourglass" : "arrow.up.circle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(canSend ? Theme.primary : Theme.textTertiary)
                }
                .disabled(!canSend)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Theme.background)
        }
    }

    private var canSend: Bool {
        !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isBusy
    }

    private func sendMessage() {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return }

        // If there's an active proposal, route to refineCandidate on the most recent active candidate
        if let activeEntryID = activeProposalEntryID,
           let activeEntry = entries.first(where: { $0.id == activeEntryID }),
           case .proposals(let block) = activeEntry.content,
           let mostRecentCandidate = block.candidates.first {
            input = ""
            refineCandidate(mostRecentCandidate, instruction: trimmed, userFacingText: trimmed)
            return
        }

        let priorMessages = messages
        appendConversationMessage(.init(role: .user, text: trimmed))
        if ideaContext.isEmpty {
            ideaContext = trimmed
        } else {
            ideaContext += "\n\(trimmed)"
        }
        input = ""

        let loadingID = appendLoading(.proposing)
        busyState = .proposing

        Task {
            let response = await appState.requestAIHabitProposals(
                recentMessages: priorMessages,
                latestUserMessage: trimmed
            )
            busyState = nil
            removeEntry(id: loadingID)

            guard let response else {
                appendError(appState.aiError ?? "I couldn't shape that into habits yet. Please try again.")
                return
            }

            appendConversationMessage(.init(role: .assistant, text: response.assistantMessage))

            if !response.candidates.isEmpty && !response.needsClarification {
                entries.append(
                    .proposalBlock(
                        whatIHeard: response.whatIHeard,
                        candidates: response.candidates,
                        state: .active
                    )
                )
            }
        }
    }

    private func createHabit(from candidate: AIHabitCandidateDTO, sourceEntryID: UUID) {
        guard !isBusy else { return }

        setProposalState(.accepted, for: sourceEntryID)
        appendConversationMessage(.init(role: .user, text: "Use This Habit: \(candidate.title)"))

        let loadingID = appendLoading(.creating)
        busyState = .creating

        Task {
            let createdHabit = await appState.createHabitFromAI(candidate: candidate)
            busyState = nil
            removeEntry(id: loadingID)

            guard let createdHabit else {
                setProposalState(.active, for: sourceEntryID)
                appendError(appState.aiError ?? appState.habitsError ?? "I couldn't save that habit. Please try again.")
                return
            }

            appendConversationMessage(.init(role: .assistant, text: "Your habit is live. You'll find it in your habits list."))
            entries.append(.success(createdHabit.name))
        }
    }

    private func refineCandidate(
        _ candidate: AIHabitCandidateDTO,
        instruction: String,
        userFacingText: String
    ) {
        guard !isBusy else { return }

        let priorMessages = messages
        let previousActiveEntryID = activeProposalEntryID
        if let previousActiveEntryID {
            setProposalState(.superseded, for: previousActiveEntryID)
        }
        appendConversationMessage(.init(role: .user, text: userFacingText))

        let loadingID = appendLoading(.refining)
        busyState = .refining

        Task {
            let response = await appState.refineAICandidate(
                idea: ideaContext.isEmpty ? candidate.description : ideaContext,
                selectedCandidate: candidate,
                refinement: instruction,
                recentMessages: priorMessages
            )
            busyState = nil
            removeEntry(id: loadingID)

            guard let response else {
                if let previousActiveEntryID {
                    setProposalState(.active, for: previousActiveEntryID)
                }
                appendError(appState.aiError ?? "I couldn't refine that habit. Please try again.")
                return
            }

            appendConversationMessage(.init(role: .assistant, text: response.assistantMessage))
            entries.append(
                .proposalBlock(
                    whatIHeard: "Updated direction for \(response.candidate.title)",
                    candidates: [response.candidate],
                    state: .active
                )
            )
        }
    }

    private func restartConversation() {
        messages = [Self.introMessage]
        entries = [.message(Self.introMessage)]
        input = ""
        ideaContext = ""
        busyState = nil
    }

    private func appendConversationMessage(_ message: AIConversationMessage) {
        messages.append(message)
        entries.append(.message(message))
    }

    private func appendLoading(_ state: AIChatBusyState) -> UUID {
        let entry = AIChatLogItem.loading(state)
        entries.append(entry)
        return entry.id
    }

    private func appendError(_ text: String) {
        entries.append(.error(text))
    }

    private func removeEntry(id: UUID) {
        entries.removeAll { $0.id == id }
    }

    private func setProposalState(_ state: AIProposalBlockState, for entryID: UUID) {
        guard let index = entries.firstIndex(where: { $0.id == entryID }) else { return }
        guard case .proposals(var block) = entries[index].content else { return }
        block.state = state
        entries[index].content = .proposals(block)
    }

    @ViewBuilder
    private func entryView(_ entry: AIChatLogItem) -> some View {
        switch entry.content {
        case .message(let message):
            bubble(message)
        case .loading(let state):
            loadingCard(state)
        case .proposals(let block):
            proposalBlockView(block, entryID: entry.id)
        case .success(let habitName):
            successCard(createdHabitName: habitName)
        case .error(let text):
            errorCard(text)
        }
    }

    @ViewBuilder
    private func bubble(_ message: AIConversationMessage) -> some View {
        HStack(alignment: .bottom) {
            if message.role == .user {
                Spacer(minLength: 48)
            }

            Text(message.text)
                .font(.subheadline)
                .foregroundColor(message.role == .user ? Theme.white : Theme.primary)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(message.role == .user ? Theme.primary : Theme.cardBeige)
                .cornerRadius(18)
                .shadow(color: Theme.shadow, radius: 3, x: 0, y: 1)
                .frame(maxWidth: 290, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant {
                Spacer(minLength: 48)
            }
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
    }

    private func loadingCard(_ state: AIChatBusyState) -> some View {
        AIChatLoadingCard(state: state)
    }

    private func proposalBlockView(_ block: AIProposalBlock, entryID: UUID) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Habit Options")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Theme.textTertiary)
                        .tracking(1.1)

                    if let whatIHeard = block.whatIHeard, !whatIHeard.isEmpty {
                        Text("What I heard")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(Theme.primary)
                        Text(whatIHeard)
                            .font(.subheadline)
                            .foregroundColor(Theme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                Spacer()

                if block.state != .active {
                    Text(block.state.badgeTitle)
                        .font(.caption2)
                        .fontWeight(.semibold)
                        .foregroundColor(block.state.badgeForeground)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(block.state.badgeBackground)
                        .cornerRadius(999)
                }
            }

            VStack(spacing: 12) {
                ForEach(block.candidates) { candidate in
                    candidateCard(candidate, isActive: block.state == .active, sourceEntryID: entryID)
                }
            }

            if block.state == .active {
                AppButton("Start Over", variant: .secondary) {
                    restartConversation()
                }
            }
        }
        .padding(16)
        .background(Theme.white)
        .cornerRadius(18)
        .overlay(
            RoundedRectangle(cornerRadius: 18)
                .stroke(block.state == .active ? Theme.border : Theme.border.opacity(0.6), lineWidth: 1)
        )
        .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
        .opacity(block.state == .active ? 1 : 0.62)
        .allowsHitTesting(block.state == .active)
    }

    private func candidateAccentColor(_ candidate: AIHabitCandidateDTO) -> Color {
        candidate.variant == "ambitious" ? Theme.terracotta : Theme.sage
    }

    private func categorySFSymbol(_ category: String) -> String {
        switch category.lowercased() {
        case "fitness":  return "figure.run"
        case "study":    return "book.closed"
        case "wellness": return "leaf"
        case "reading":  return "text.book.closed"
        case "sleep":    return "moon"
        default:         return "star"
        }
    }

    private func candidateCard(
        _ candidate: AIHabitCandidateDTO,
        isActive: Bool,
        sourceEntryID: UUID
    ) -> some View {
        let accent = candidateAccentColor(candidate)
        let isAmbitious = candidate.variant == "ambitious"

        return VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: categorySFSymbol(candidate.category))
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(accent)
                    .frame(width: 38, height: 38)
                    .background(accent.opacity(0.15))
                    .cornerRadius(10)

                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(candidate.title)
                            .font(.headline)
                            .fontWeight(isAmbitious ? .bold : .semibold)
                            .foregroundColor(Theme.primary)
                        Text(isAmbitious ? "Ambitious" : "Balanced")
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundColor(accent)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3)
                            .background(accent.opacity(0.12))
                            .cornerRadius(999)
                    }
                    Text(candidate.description)
                        .font(.subheadline)
                        .foregroundColor(Theme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 0)
            }

            HStack(spacing: 10) {
                candidateMetaPill(icon: "calendar", text: formattedSchedule(candidate.suggestedSchedule), accent: accent)
                candidateMetaPill(icon: "timer", text: "\(candidate.durationMinutes) min", accent: accent)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Why this fits")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(Theme.textTertiary)
                    .tracking(0.8)
                Text(candidate.rationale)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if isActive {
                AppButton("Use This Habit", variant: .primary) {
                    createHabit(from: candidate, sourceEntryID: sourceEntryID)
                }
            }
        }
        .padding(14)
        .background(Theme.cardBeige.opacity(isActive ? 1 : 0.72))
        .cornerRadius(14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(accent.opacity(isAmbitious ? 0.35 : 0), lineWidth: 1.5)
        )
    }

    /// Converts a free-text schedule string from the AI into a compact readable form.
    /// "Monday, Wednesday, Friday" → "Mon/Wed/Fri"
    /// "3 times per week" → "3×/week"
    /// "daily" → "Daily"
    private func formattedSchedule(_ raw: String) -> String {
        let lowered = raw.lowercased()

        // Map full day names to 3-letter abbreviations, in calendar order
        let dayMap: [(full: String, abbr: String)] = [
            ("sunday", "Sun"), ("monday", "Mon"), ("tuesday", "Tue"),
            ("wednesday", "Wed"), ("thursday", "Thu"), ("friday", "Fri"), ("saturday", "Sat")
        ]

        // Collect any day names found, preserving their position in the string
        var found: [(pos: String.Index, abbr: String)] = []
        for day in dayMap {
            if let r = lowered.range(of: day.full) {
                found.append((pos: r.lowerBound, abbr: day.abbr))
            }
        }
        if !found.isEmpty {
            return found.sorted { $0.pos < $1.pos }.map(\.abbr).joined(separator: "/")
        }

        // "X times per week" or "X time per week"
        let parts = lowered.components(separatedBy: .whitespaces)
        if let idx = parts.firstIndex(where: { $0 == "times" || $0 == "time" }),
           idx > 0, let n = Int(parts[idx - 1]) {
            return "\(n)×/week"
        }

        if lowered.contains("daily") || lowered.contains("every day") { return "Daily" }
        if lowered.contains("weekday") { return "Mon–Fri" }
        if lowered.contains("weekend") { return "Sat/Sun" }

        // Fallback: first 3 words
        return parts.prefix(3).joined(separator: " ")
    }

    private func candidateMetaPill(icon: String, text: String, accent: Color = Theme.primary) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12, weight: .medium))
            Text(text)
                .font(.caption)
                .fontWeight(.semibold)
                .lineLimit(1)
        }
        .foregroundColor(accent)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Theme.white)
        .cornerRadius(999)
    }

    private func proposalActionButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(Theme.primary)
                .frame(maxWidth: .infinity)
                .frame(height: 38)
                .background(Theme.white)
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(Theme.border, lineWidth: 1)
                )
                .cornerRadius(10)
        }
        .buttonStyle(.plain)
    }

    private func successCard(createdHabitName: String) -> some View {
        VStack(spacing: 16) {
            ZStack {
                Circle().fill(Theme.sageLight).frame(width: 60, height: 60)
                Image(systemName: "checkmark")
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(Theme.primary)
            }

            VStack(spacing: 6) {
                Text("Habit Created")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(Theme.primary)
                Text("\(createdHabitName) has been added to your habits.")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .multilineTextAlignment(.center)
            }

            AppButton("Generate Another Habit", variant: .secondary) {
                restartConversation()
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Theme.white)
        .cornerRadius(18)
        .shadow(color: Theme.shadow, radius: 10, x: 0, y: 3)
    }

    private func errorCard(_ text: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(Theme.terracotta)
            Text(text)
                .font(.subheadline)
                .foregroundColor(Theme.primary)
            Spacer()
        }
        .padding(14)
        .background(Theme.terracotta.opacity(0.08))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Theme.terracotta.opacity(0.2), lineWidth: 1)
        )
    }
}

private enum AIChatBusyState {
    case proposing
    case refining
    case creating

    var rotatingMessages: [String] {
        switch self {
        case .proposing:
            return ["Thinking...", "Working...", "Shaping your habit...", "Building options..."]
        case .refining:
            return ["Refining...", "Adjusting the habit...", "Making it fit better...", "Reworking the option..."]
        case .creating:
            return ["Saving...", "Locking it in...", "Adding it to FollowThru...", "Almost there..."]
        }
    }
}

private enum AIProposalBlockState {
    case active
    case superseded
    case accepted

    var badgeTitle: String {
        switch self {
        case .active:
            return ""
        case .superseded:
            return "Superseded"
        case .accepted:
            return "Selected"
        }
    }

    var badgeForeground: Color {
        switch self {
        case .active:
            return .clear
        case .superseded:
            return Theme.textSecondary
        case .accepted:
            return Theme.success
        }
    }

    var badgeBackground: Color {
        switch self {
        case .active:
            return .clear
        case .superseded:
            return Theme.cardBeige
        case .accepted:
            return Theme.sageLight
        }
    }
}

private struct AIProposalBlock {
    let whatIHeard: String?
    let candidates: [AIHabitCandidateDTO]
    var state: AIProposalBlockState
}

private struct AIChatLogItem: Identifiable {
    enum Content {
        case message(AIConversationMessage)
        case loading(AIChatBusyState)
        case proposals(AIProposalBlock)
        case success(String)
        case error(String)
    }

    let id: UUID
    var content: Content

    init(id: UUID = UUID(), content: Content) {
        self.id = id
        self.content = content
    }

    static func message(_ message: AIConversationMessage) -> AIChatLogItem {
        AIChatLogItem(content: .message(message))
    }

    static func loading(_ state: AIChatBusyState) -> AIChatLogItem {
        AIChatLogItem(content: .loading(state))
    }

    static func proposalBlock(
        whatIHeard: String?,
        candidates: [AIHabitCandidateDTO],
        state: AIProposalBlockState
    ) -> AIChatLogItem {
        AIChatLogItem(
            content: .proposals(
                AIProposalBlock(
                    whatIHeard: whatIHeard,
                    candidates: candidates,
                    state: state
                )
            )
        )
    }

    static func success(_ createdHabitName: String) -> AIChatLogItem {
        AIChatLogItem(content: .success(createdHabitName))
    }

    static func error(_ text: String) -> AIChatLogItem {
        AIChatLogItem(content: .error(text))
    }
}

private struct AIChatLoadingCard: View {
    let state: AIChatBusyState

    @State private var currentIndex = 0
    private let timer = Timer.publish(every: 0.95, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            ProgressView()
                .progressViewStyle(.circular)
                .tint(Theme.primary)

            Text(state.rotatingMessages[currentIndex])
                .font(.subheadline)
                .foregroundColor(Theme.primary)

            Spacer(minLength: 0)
        }
        .padding(14)
        .background(Theme.cardBeige)
        .cornerRadius(16)
        .shadow(color: Theme.shadow, radius: 3, x: 0, y: 1)
        .frame(maxWidth: .infinity, alignment: .leading)
        .onReceive(timer) { _ in
            currentIndex = (currentIndex + 1) % state.rotatingMessages.count
        }
    }
}

private struct AnimatedComposerPlaceholder: View {
    let text: String

    @State private var availableWidth: CGFloat = 0
    @State private var textWidth: CGFloat = 0
    @State private var animate = false

    private var targetOffset: CGFloat { min(0, availableWidth - textWidth) }

    var body: some View {
        GeometryReader { geometry in
            Text(text)
                .font(.body)
                .foregroundColor(Theme.textTertiary)
                .lineLimit(1)
                .background(
                    GeometryReader { textGeometry in
                        Color.clear
                            .onAppear {
                                textWidth = textGeometry.size.width
                                availableWidth = geometry.size.width
                                restartAnimation()
                            }
                            .onChange(of: textGeometry.size.width, initial: false) { _, newValue in
                                textWidth = newValue
                                restartAnimation()
                            }
                    }
                )
                .offset(x: animate && textWidth > availableWidth ? targetOffset : 0)
                .animation(
                    textWidth > availableWidth
                        ? .linear(duration: max(4, Double(textWidth - availableWidth) / 18)).repeatForever(autoreverses: true)
                        : .default,
                    value: animate
                )
                .onAppear {
                    availableWidth = geometry.size.width
                    restartAnimation()
                }
                .onChange(of: geometry.size.width, initial: false) { _, newValue in
                    availableWidth = newValue
                    restartAnimation()
                }
        }
        .frame(height: 22)
        .clipped()
        .allowsHitTesting(false)
    }

    private func restartAnimation() {
        animate = false
        guard textWidth > availableWidth else { return }
        DispatchQueue.main.async {
            animate = true
        }
    }
}
