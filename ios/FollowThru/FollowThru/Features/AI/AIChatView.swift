import SwiftUI

struct AIChatView: View {
    @EnvironmentObject var appState: AppState

    @State private var messages: [AIConversationMessage] = [AIChatView.introMessage]
    @State private var draft = AIIntakeDraftDTO()
    @State private var phase: AIConversationPhase = .intake
    @State private var input = ""
    @State private var preview: AIPlanPreview? = nil
    @State private var previewBeforeRevision: AIPlanPreview? = nil
    @State private var confirmationSummary: String? = nil
    @State private var createdHabitName: String? = nil
    @State private var errorMessage: String? = nil
    @State private var pendingAction: PendingAction? = nil

    private enum PendingAction {
        case intake, generating, revising, creating
    }

    private static let introMessage = AIConversationMessage(
        role: .assistant,
        text: "What's a habit you've been meaning to make stick? Tell me whatever's on your mind — I'll shape it into a plan."
    )

    private var isBusy: Bool { pendingAction != nil }

    private var showsComposer: Bool {
        switch phase {
        case .intake, .confirming, .revising: return true
        case .preview, .created:              return false
        }
    }

    private var composerPlaceholder: String {
        switch phase {
        case .intake:            return "Describe the habit you want to build..."
        case .confirming:        return "Confirm, or tell me what to change..."
        case .revising:          return "What would you like to tweak?"
        case .preview, .created: return ""
        }
    }

    // MARK: – Body

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 14) {
                            ForEach(messages) { message in
                                bubble(message)
                            }

                            if let errorMessage {
                                errorCard(errorMessage)
                            }

                            if let confirmationSummary, phase == .confirming {
                                confirmationCard(summary: confirmationSummary)
                            }

                            if pendingAction == .generating {
                                loadingCard(title: "Building Your Plan",
                                            message: "Turning your inputs into a realistic starter plan.")
                            }
                            if pendingAction == .creating {
                                loadingCard(title: "Creating Habit",
                                            message: "Saving your plan to your habits list.")
                            }
                            if pendingAction == .revising {
                                loadingCard(title: "Revising Plan",
                                            message: "Updating the plan based on your feedback.")
                            }

                            if let preview, phase == .preview {
                                previewCard(preview)
                            }

                            if let createdHabitName, phase == .created {
                                successCard(createdHabitName: createdHabitName)
                            }

                            Color.clear.frame(height: 1).id("bottom")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                    }
                    .onChange(of: messages.count, initial: false) { _, _ in
                        withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                    }
                    .onChange(of: phase, initial: false) { _, _ in
                        withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                    }
                }

                if showsComposer { composerBar }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("AI Coach")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    // MARK: – Composer bar

    private var composerBar: some View {
        VStack(spacing: 0) {
            Divider().background(Theme.border)
            HStack(alignment: .bottom, spacing: 10) {
                ZStack(alignment: .leading) {
                    if input.isEmpty, !composerPlaceholder.isEmpty {
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

    // MARK: – Message routing

    private func sendMessage() {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return }
        let priorMessages = messages
        messages.append(AIConversationMessage(role: .user, text: trimmed))
        input = ""
        errorMessage = nil

        switch phase {
        case .intake:
            handleIntakeTurn(userMessage: trimmed, priorMessages: priorMessages)
        case .confirming:
            if isAffirmative(trimmed) {
                generatePlanFromDraft()
            } else {
                handleIntakeTurn(userMessage: trimmed, priorMessages: priorMessages)
            }
        case .revising:
            revisePlan(critique: trimmed, priorMessages: priorMessages)
        case .preview, .created:
            break
        }
    }

    // MARK: – Async actions

    private func handleIntakeTurn(userMessage: String, priorMessages: [AIConversationMessage]) {
        pendingAction = .intake
        Task {
            let response = await appState.submitAIIntake(
                recentMessages: priorMessages,
                currentDraft: draft,
                latestUserMessage: userMessage
            )
            pendingAction = nil
            guard let response else {
                errorMessage = appState.aiError ?? "Something went wrong. Please try again."
                return
            }
            draft = response.updatedDraft
            confirmationSummary = response.confirmationSummary
            messages.append(AIConversationMessage(role: .assistant, text: response.assistantMessage))
            phase = response.readyForConfirmation ? .confirming : .intake
        }
    }

    private func generatePlanFromDraft() {
        guard !isBusy else { return }
        pendingAction = .generating
        errorMessage = nil
        preview = nil
        createdHabitName = nil
        Task {
            let generatedPreview = await appState.requestAIPlan(from: draft)
            pendingAction = nil
            if let generatedPreview {
                preview = generatedPreview
                phase = .preview
                messages.append(AIConversationMessage(role: .assistant, text: "Your plan is ready. Take a look below."))
            } else {
                errorMessage = appState.aiError ?? "Plan generation failed. Please try again."
            }
        }
    }

    private func createHabit() {
        guard !isBusy else { return }
        pendingAction = .creating
        errorMessage = nil
        Task {
            let createdHabit = await appState.createHabitFromAI(draft: draft)
            pendingAction = nil
            if let createdHabit {
                preview = appState.latestAIPlan ?? preview
                createdHabitName = createdHabit.name
                phase = .created
                messages.append(AIConversationMessage(role: .assistant, text: "Your habit is live. You'll find it in your habits list."))
            } else {
                errorMessage = appState.aiError ?? appState.habitsError ?? "Please try again."
            }
        }
    }

    private func beginRevision() {
        guard let preview else { return }
        errorMessage = nil
        previewBeforeRevision = preview
        self.preview = nil
        phase = .revising
        messages.append(AIConversationMessage(role: .assistant, text: "What would you like to change?"))
    }

    private func revisePlan(critique: String, priorMessages: [AIConversationMessage]) {
        guard let activePreview = previewBeforeRevision ?? preview else { return }
        pendingAction = .revising
        errorMessage = nil
        Task {
            let response = await appState.reviseAIPlan(
                draft: draft,
                currentPlan: activePreview,
                critique: critique,
                recentMessages: priorMessages
            )
            pendingAction = nil
            guard let response else {
                preview = previewBeforeRevision ?? activePreview
                previewBeforeRevision = nil
                phase = .preview
                errorMessage = appState.aiError ?? "Please try again."
                return
            }
            if response.action == "plan_tweak", let planTweak = response.planTweak {
                self.preview = planTweak.toAIPlanPreview()
                previewBeforeRevision = nil
                phase = .preview
                messages.append(AIConversationMessage(role: .assistant, text: "Here's the revised plan."))
                return
            }
            if let reopened = response.reopenIntake {
                self.preview = nil
                previewBeforeRevision = nil
                draft = reopened.updatedDraft
                confirmationSummary = reopened.confirmationSummary
                phase = reopened.readyForConfirmation ? .confirming : .intake
                messages.append(AIConversationMessage(role: .assistant, text: reopened.assistantMessage))
                return
            }
            preview = previewBeforeRevision ?? activePreview
            previewBeforeRevision = nil
            phase = .preview
            errorMessage = "Please try again."
        }
    }

    private func restartConversation() {
        messages = [Self.introMessage]
        draft = AIIntakeDraftDTO()
        phase = .intake
        input = ""
        preview = nil
        previewBeforeRevision = nil
        confirmationSummary = nil
        createdHabitName = nil
        errorMessage = nil
        pendingAction = nil
    }

    private func isAffirmative(_ text: String) -> Bool {
        ["yes", "y", "confirm", "confirmed", "looks good", "sounds good", "go ahead", "generate"]
            .contains(text.lowercased())
    }

    // MARK: – Chat bubble

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
                .frame(maxWidth: 280, alignment: message.role == .user ? .trailing : .leading)

            if message.role == .assistant { Spacer(minLength: 48) }
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
    }

    // MARK: – Confirmation card

    private func confirmationCard(summary: String) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            let lines = summary.components(separatedBy: "\n").filter { !$0.isEmpty }
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(lines.enumerated()), id: \.offset) { _, line in
                    if line.hasPrefix("- ") {
                        HStack(alignment: .top, spacing: 8) {
                            Circle().fill(Theme.sage).frame(width: 5, height: 5).padding(.top, 6)
                            Text(line.dropFirst(2))
                                .font(.subheadline)
                                .foregroundColor(Theme.primary)
                        }
                    } else {
                        Text(line)
                            .font(.subheadline)
                            .fontWeight(line.contains("captured") || line.contains("Here") ? .semibold : .regular)
                            .foregroundColor(Theme.primary)
                    }
                }
            }

            Divider().background(Theme.border)

            AppButton("Generate Plan", variant: .primary) {
                generatePlanFromDraft()
            }
            .disabled(isBusy)
            .opacity(isBusy ? 0.6 : 1)
        }
        .padding(16)
        .background(Theme.white)
        .cornerRadius(16)
        .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
    }

    // MARK: – Plan preview card  (mirrors the "Your Plan is Ready" screen in the Figma)

    private func previewCard(_ planPreview: AIPlanPreview) -> some View {
        VStack(alignment: .leading, spacing: 0) {

            // Plan identity block (warm beige background)
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top) {
                    Image(systemName: planPreview.category.sfSymbol)
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(Theme.primary)
                        .frame(width: 38, height: 38)
                        .background(Theme.sageLight)
                        .cornerRadius(10)
                    Spacer()
                    Text(planPreview.category.displayName)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Theme.primary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Theme.sageLight)
                        .cornerRadius(999)
                }

                Text(planPreview.title)
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(Theme.primary)

                Text(planPreview.description)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(14)
            .background(Theme.cardBeige)
            .cornerRadius(12)

            Spacer().frame(height: 18)

            // Schedule
            previewSectionLabel("SCHEDULE")
            Spacer().frame(height: 8)
            VStack(spacing: 0) {
                previewScheduleRow(icon: "clock", text: formattedTime(planPreview.triggerValue))
                Divider().background(Theme.border).padding(.leading, 38)
                previewScheduleRow(icon: "calendar", text: planPreview.frequencySummary)
            }
            .background(Theme.white)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))

            Spacer().frame(height: 18)

            // Growth plan
            previewSectionLabel("YOUR GROWTH PLAN")
            Spacer().frame(height: 8)
            VStack(spacing: 0) {
                let sorted = planPreview.progressions.sorted { $0.week < $1.week }
                ForEach(Array(sorted.enumerated()), id: \.element.week) { index, step in
                    if index > 0 {
                        Divider().background(Theme.border).padding(.leading, 46)
                    }
                    previewProgressionRow(step: step)
                }
            }
            .background(Theme.white)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))

            Spacer().frame(height: 22)

            // Action buttons
            VStack(spacing: 10) {
                AppButton("Activate Habit", variant: .primary) {
                    createHabit()
                }
                .disabled(isBusy)
                .opacity(isBusy ? 0.6 : 1)

                AppButton("Tweak it", variant: .secondary) {
                    beginRevision()
                }
            }
        }
        .padding(16)
        .background(Theme.white)
        .cornerRadius(18)
        .shadow(color: Theme.shadow, radius: 10, x: 0, y: 3)
    }

    @ViewBuilder
    private func previewSectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(Theme.textTertiary)
            .tracking(1.4)
    }

    @ViewBuilder
    private func previewScheduleRow(icon: String, text: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(Theme.sage)
                .frame(width: 20)
            Text(text)
                .font(.subheadline)
                .foregroundColor(Theme.primary)
            Spacer()
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 13)
    }

    @ViewBuilder
    private func previewProgressionRow(step: AIProgressionDTO) -> some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                Circle().fill(Theme.sageLight).frame(width: 32, height: 32)
                Text("W\(step.week)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(Theme.primary)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text("Week \(step.week)")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(Theme.textTertiary)
                Text(step.description)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    // MARK: – Success card

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
                    .font(.title3).fontWeight(.bold)
                    .foregroundColor(Theme.primary)
                Text("\(createdHabitName) has been added to your habits.")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .multilineTextAlignment(.center)
            }
            AppButton("Build Another Habit", variant: .secondary) {
                restartConversation()
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(Theme.white)
        .cornerRadius(18)
        .shadow(color: Theme.shadow, radius: 10, x: 0, y: 3)
    }

    // MARK: – Loading card

    private func loadingCard(title: String, message: String) -> some View {
        HStack(spacing: 14) {
            ProgressView().tint(Theme.primary)
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.subheadline).fontWeight(.semibold)
                    .foregroundColor(Theme.primary)
                Text(message)
                    .font(.caption)
                    .foregroundColor(Theme.textSecondary)
            }
            Spacer()
        }
        .padding(14)
        .background(Theme.cardBeige)
        .cornerRadius(14)
    }

    // MARK: – Error card

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
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.terracotta.opacity(0.2), lineWidth: 1))
    }

    // MARK: – Time formatter

    private func formattedTime(_ value: String) -> String {
        guard let date = BackendHabitMapper.time(from: value) else { return value }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

// MARK: – Animated placeholder

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
        DispatchQueue.main.async { animate = true }
    }
}
