import SwiftUI
import Combine

struct AIChatView: View {
    @EnvironmentObject var appState: AppState

    // Session state — draft is passed to the backend every turn and updated from the response.
    @State private var draft = AIIntakeDraftDTO()
    @State private var messages: [AIConversationMessage] = [AIChatView.introMessage]
    @State private var entries: [AIChatLogItem] = [.message(AIChatView.introMessage)]
    @State private var input = ""
    @State private var isBusy = false

    private static let introMessage = AIConversationMessage(
        role: .assistant,
        text: "I'm your FollowThru habit coach. Tell me what kind of change you want in your life — what you want to do, how often, and anything that would make it realistic or unrealistic for you."
    )

    private var hasSuccessEntry: Bool {
        entries.contains { if case .success = $0.content { return true }; return false }
    }

    private var showsComposer: Bool { !isBusy && !hasSuccessEntry }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 14) {
                            ForEach(entries) { entry in
                                entryView(entry).id(entry.id)
                            }
                            Color.clear.frame(height: 1).id("bottom")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }
                    .onChange(of: entries.count, initial: false) { _, _ in
                        withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom", anchor: .bottom) }
                    }
                    .onAppear { proxy.scrollTo("bottom", anchor: .bottom) }
                }

                if showsComposer { composerBar }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Habit Coach")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    // MARK: - Composer

    private var composerBar: some View {
        VStack(spacing: 0) {
            Divider().background(Theme.border)
            HStack(alignment: .bottom, spacing: 10) {
                ZStack(alignment: .leading) {
                    if input.isEmpty {
                        AnimatedComposerPlaceholder(text: "Tell me what kind of change you want to make...")
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
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))

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

    // MARK: - Send

    private func sendMessage() {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return }

        appendConversationMessage(.init(role: .user, text: trimmed))
        input = ""

        let loadingID = appendLoading()
        isBusy = true

        let currentDraft = draft
        let priorMessages = messages

        Task {
            let response = await appState.sendChatMessage(
                message: trimmed,
                draft: currentDraft,
                recentMessages: priorMessages
            )
            isBusy = false
            removeEntry(id: loadingID)

            guard let response else {
                appendError(appState.aiError ?? "Something went wrong. Please try again.")
                return
            }

            // Always update draft with whatever the backend extracted this turn
            draft = response.updatedDraft

            appendConversationMessage(.init(role: .assistant, text: response.assistantMessage))

            if response.action == "generate", !response.candidates.isEmpty {
                entries.append(.proposalBlock(candidates: response.candidates, state: .active))
            }
        }
    }

    private func createHabit(from candidate: AIChatCandidateDTO, sourceEntryID: UUID) {
        guard !isBusy else { return }

        setProposalState(.accepted, for: sourceEntryID)
        appendConversationMessage(.init(role: .user, text: "Use This Habit: \(candidate.title)"))

        let loadingID = appendLoading()
        isBusy = true

        Task {
            let createdHabit = await appState.createHabitFromChatCandidate(candidate)
            isBusy = false
            removeEntry(id: loadingID)

            guard let createdHabit else {
                setProposalState(.active, for: sourceEntryID)
                appendError(appState.aiError ?? appState.habitsError ?? "Couldn't save that habit. Please try again.")
                return
            }

            appendConversationMessage(.init(role: .assistant, text: "Your habit is live. You'll find it in your habits list."))
            entries.append(.success(createdHabit.name))
        }
    }

    private func restartConversation() {
        draft = AIIntakeDraftDTO()
        messages = [Self.introMessage]
        entries = [.message(Self.introMessage)]
        input = ""
        isBusy = false
    }

    // MARK: - Entry helpers

    private func appendConversationMessage(_ message: AIConversationMessage) {
        messages.append(message)
        entries.append(.message(message))
    }

    private func appendLoading() -> UUID {
        let entry = AIChatLogItem.loading()
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

    // MARK: - Entry views

    @ViewBuilder
    private func entryView(_ entry: AIChatLogItem) -> some View {
        switch entry.content {
        case .message(let message):      bubble(message)
        case .loading:                   loadingCard()
        case .proposals(let block):      proposalBlockView(block, entryID: entry.id)
        case .success(let habitName):    successCard(createdHabitName: habitName)
        case .error(let text):           errorCard(text)
        }
    }

    @ViewBuilder
    private func bubble(_ message: AIConversationMessage) -> some View {
        HStack(alignment: .bottom) {
            if message.role == .user { Spacer(minLength: 48) }

            Text(message.text)
                .font(.subheadline)
                .foregroundColor(message.role == .user ? Theme.white : Theme.primary)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(message.role == .user ? Theme.primary : Theme.cardBeige)
                .cornerRadius(18)
                .shadow(color: Theme.shadow, radius: 3, x: 0, y: 1)
                .frame(maxWidth: 290, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant { Spacer(minLength: 48) }
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
    }

    private func loadingCard() -> some View {
        AIChatLoadingCard()
    }

    private func proposalBlockView(_ block: AIProposalBlock, entryID: UUID) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                Text("Habit Options")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(Theme.textTertiary)
                    .tracking(1.1)

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
                AppButton("Start Over", variant: .secondary) { restartConversation() }
            }
        }
        .padding(16)
        .background(Theme.white)
        .cornerRadius(18)
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.border.opacity(block.state == .active ? 1 : 0.6), lineWidth: 1))
        .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
        .opacity(block.state == .active ? 1 : 0.62)
        .allowsHitTesting(block.state == .active)
    }

    private func candidateCard(
        _ candidate: AIChatCandidateDTO,
        isActive: Bool,
        sourceEntryID: UUID
    ) -> some View {
        let accent = candidate.variant == "ambitious" ? Theme.terracotta : Theme.sage
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
                metaPill(icon: "calendar", text: formattedSchedule(candidate.suggestedSchedule), accent: accent)
                if let target = candidate.habitPayload.targetValue,
                   let unit = candidate.habitPayload.quantityUnit {
                    // Tracked/cumulative habit — show the quantity goal, not a duration
                    metaPill(icon: "checkmark.circle", text: "\(formatTarget(target)) \(unit)", accent: accent)
                } else if candidate.durationMinutes > 0 {
                    // Session habit — show duration
                    metaPill(icon: "timer", text: formatDuration(candidate.durationMinutes), accent: accent)
                }
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
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(accent.opacity(isAmbitious ? 0.35 : 0), lineWidth: 1.5))
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
                    .font(.title3).fontWeight(.bold).foregroundColor(Theme.primary)
                Text("\(createdHabitName) has been added to your habits.")
                    .font(.subheadline).foregroundColor(Theme.textSecondary)
                    .multilineTextAlignment(.center)
            }
            AppButton("Generate Another Habit", variant: .secondary) { restartConversation() }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Theme.white)
        .cornerRadius(18)
        .shadow(color: Theme.shadow, radius: 10, x: 0, y: 3)
    }

    private func errorCard(_ text: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundColor(Theme.terracotta)
            Text(text).font(.subheadline).foregroundColor(Theme.primary)
            Spacer()
        }
        .padding(14)
        .background(Theme.terracotta.opacity(0.08))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.terracotta.opacity(0.2), lineWidth: 1))
    }

    // MARK: - Formatting helpers

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

    private func formatTarget(_ value: Double) -> String {
        value == value.rounded() ? String(Int(value)) : String(format: "%.1f", value)
    }

    private func formatDuration(_ minutes: Int) -> String {
        if minutes < 60 { return "\(minutes) min" }
        let h = minutes / 60, m = minutes % 60
        return m == 0 ? "\(h)h" : "\(h)h \(m)m"
    }

    private func formattedSchedule(_ raw: String) -> String {
        let lower = raw.lowercased()
        let dayMap: [(full: String, abbr: String)] = [
            ("sunday","Sun"),("monday","Mon"),("tuesday","Tue"),
            ("wednesday","Wed"),("thursday","Thu"),("friday","Fri"),("saturday","Sat")
        ]
        var found: [(pos: String.Index, abbr: String)] = []
        for day in dayMap {
            if let r = lower.range(of: day.full) { found.append((pos: r.lowerBound, abbr: day.abbr)) }
        }
        if !found.isEmpty { return found.sorted { $0.pos < $1.pos }.map(\.abbr).joined(separator: "/") }
        let parts = lower.components(separatedBy: .whitespaces)
        if let idx = parts.firstIndex(where: { $0 == "times" || $0 == "time" }),
           idx > 0, let n = Int(parts[idx - 1]) { return "\(n)×/week" }
        if lower.contains("daily") || lower.contains("every day") { return "Daily" }
        if lower.contains("weekday") { return "Mon–Fri" }
        if lower.contains("weekend") { return "Sat/Sun" }
        return parts.prefix(3).joined(separator: " ")
    }

    private func metaPill(icon: String, text: String, accent: Color = Theme.primary) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon).font(.system(size: 12, weight: .medium))
            Text(text).font(.caption).fontWeight(.semibold).lineLimit(1)
        }
        .foregroundColor(accent)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(Theme.white)
        .cornerRadius(999)
    }
}

// MARK: - Supporting types

private enum AIProposalBlockState {
    case active, superseded, accepted

    var badgeTitle: String {
        switch self { case .active: return ""; case .superseded: return "Superseded"; case .accepted: return "Selected" }
    }
    var badgeForeground: Color {
        switch self { case .active: return .clear; case .superseded: return Theme.textSecondary; case .accepted: return Theme.success }
    }
    var badgeBackground: Color {
        switch self { case .active: return .clear; case .superseded: return Theme.cardBeige; case .accepted: return Theme.sageLight }
    }
}

private struct AIProposalBlock {
    let candidates: [AIChatCandidateDTO]
    var state: AIProposalBlockState
}

private struct AIChatLogItem: Identifiable {
    enum Content {
        case message(AIConversationMessage)
        case loading
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
    static func loading() -> AIChatLogItem { AIChatLogItem(content: .loading) }
    static func proposalBlock(candidates: [AIChatCandidateDTO], state: AIProposalBlockState) -> AIChatLogItem {
        AIChatLogItem(content: .proposals(AIProposalBlock(candidates: candidates, state: state)))
    }
    static func success(_ createdHabitName: String) -> AIChatLogItem { AIChatLogItem(content: .success(createdHabitName)) }
    static func error(_ text: String) -> AIChatLogItem { AIChatLogItem(content: .error(text)) }
}

private struct AIChatLoadingCard: View {
    @State private var index = 0
    private let messages = ["Thinking...", "Working on it...", "Shaping your habit...", "Building options..."]
    private let timer = Timer.publish(every: 0.95, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            ProgressView().progressViewStyle(.circular).tint(Theme.primary)
            Text(messages[index]).font(.subheadline).foregroundColor(Theme.primary)
            Spacer(minLength: 0)
        }
        .padding(14)
        .background(Theme.cardBeige)
        .cornerRadius(16)
        .shadow(color: Theme.shadow, radius: 3, x: 0, y: 1)
        .frame(maxWidth: .infinity, alignment: .leading)
        .onReceive(timer) { _ in index = (index + 1) % messages.count }
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
                .background(GeometryReader { tg in
                    Color.clear
                        .onAppear { textWidth = tg.size.width; availableWidth = geometry.size.width; restart() }
                        .onChange(of: tg.size.width, initial: false) { _, v in textWidth = v; restart() }
                })
                .offset(x: animate && textWidth > availableWidth ? targetOffset : 0)
                .animation(
                    textWidth > availableWidth
                        ? .linear(duration: max(4, Double(textWidth - availableWidth) / 18)).repeatForever(autoreverses: true)
                        : .default,
                    value: animate
                )
                .onAppear { availableWidth = geometry.size.width; restart() }
                .onChange(of: geometry.size.width, initial: false) { _, v in availableWidth = v; restart() }
        }
        .frame(height: 22)
        .clipped()
        .allowsHitTesting(false)
    }

    private func restart() {
        animate = false
        guard textWidth > availableWidth else { return }
        DispatchQueue.main.async { animate = true }
    }
}
