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
        case intake
        case generating
        case revising
        case creating
    }

    private static let introMessage = AIConversationMessage(
        role: .assistant,
        text: "I’m your FollowThru habit coach. I’ll help you turn a habit idea into a realistic plan. Start by telling me the habit you want to build and a short description of what that habit looks like for you."
    )

    private var isBusy: Bool {
        pendingAction != nil
    }

    private var showsComposer: Bool {
        switch phase {
        case .intake, .confirming, .revising:
            return true
        case .preview, .created:
            return false
        }
    }

    private var composerPlaceholder: String {
        switch phase {
        case .intake:
            return "Tell me about the habit you want to build..."
        case .confirming:
            return "Reply with a change, or type confirm..."
        case .revising:
            return "Tell me what you want changed..."
        case .preview, .created:
            return ""
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(spacing: 16) {
                            ForEach(messages) { message in
                                bubble(message)
                            }

                            if let errorMessage {
                                messageCard(
                                    title: "Something went wrong",
                                    text: errorMessage,
                                    icon: "exclamationmark.triangle.fill",
                                    color: Theme.terracotta
                                )
                            }

                            if let confirmationSummary, phase == .confirming {
                                confirmationCard(summary: confirmationSummary)
                            }

                            if pendingAction == .generating {
                                loadingCard(
                                    title: "Generating Plan",
                                    message: "Turning your confirmed intake into a realistic starter plan."
                                )
                            }

                            if pendingAction == .creating {
                                loadingCard(
                                    title: "Creating Habit",
                                    message: "Saving your AI plan into your habits list."
                                )
                            }

                            if pendingAction == .revising {
                                loadingCard(
                                    title: "Revising Plan",
                                    message: "Updating the plan based on your feedback."
                                )
                            }

                            if let preview, phase == .preview {
                                previewCard(preview)
                            }

                            if let createdHabitName, phase == .created {
                                successCard(createdHabitName: createdHabitName)
                            }

                            Color.clear
                                .frame(height: 1)
                                .id("bottom")
                        }
                        .padding()
                    }
                    .onChange(of: messages.count, initial: false) { _, _ in
                        withAnimation {
                            proxy.scrollTo("bottom", anchor: .bottom)
                        }
                    }
                    .onChange(of: phase, initial: false) { _, _ in
                        withAnimation {
                            proxy.scrollTo("bottom", anchor: .bottom)
                        }
                    }
                }

                if showsComposer {
                    Divider()
                    composer
                }
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("AI Coach")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 10) {
            ZStack(alignment: .leading) {
                if input.isEmpty, !composerPlaceholder.isEmpty {
                    AnimatedComposerPlaceholder(text: composerPlaceholder)
                        .padding(.horizontal, 12)
                }

                TextField("", text: $input, axis: .vertical)
                    .lineLimit(1...4)
                    .padding(12)
            }
            .background(Theme.white)
            .cornerRadius(14)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Theme.lightGray)
            )

            Button(action: sendMessage) {
                Image(systemName: isBusy ? "hourglass" : "arrow.up.circle.fill")
                    .font(.system(size: 32))
                    .foregroundColor(canSend ? Theme.primary : Theme.textSecondary)
            }
            .disabled(!canSend)
        }
        .padding()
        .background(Theme.offWhite)
    }

    private var canSend: Bool {
        !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isBusy
    }

    private func sendMessage() {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return }

        let priorMessages = messages
        let userMessage = AIConversationMessage(role: .user, text: trimmed)
        messages.append(userMessage)
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
                errorMessage = appState.aiError ?? "Please try again."
                return
            }

            draft = response.updatedDraft
            confirmationSummary = response.confirmationSummary
            messages.append(
                AIConversationMessage(
                    role: .assistant,
                    text: response.assistantMessage
                )
            )
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
                messages.append(
                    AIConversationMessage(
                        role: .assistant,
                        text: "Here’s a plan draft based on what you told me. Review it and decide what you want to do next."
                    )
                )
            } else {
                errorMessage = appState.aiError ?? "Please try again."
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
                messages.append(
                    AIConversationMessage(
                        role: .assistant,
                        text: "Your habit is ready. You can find it in your habits list now."
                    )
                )
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
        messages.append(
            AIConversationMessage(
                role: .assistant,
                text: "Tell me what you want changed, and I’ll either revise the plan or reopen intake if the core inputs need updating."
            )
        )
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
                messages.append(
                    AIConversationMessage(
                        role: .assistant,
                        text: "I revised the plan. Take a look and see if this version feels closer."
                    )
                )
                return
            }

            if let reopened = response.reopenIntake {
                self.preview = nil
                previewBeforeRevision = nil
                draft = reopened.updatedDraft
                confirmationSummary = reopened.confirmationSummary
                phase = reopened.readyForConfirmation ? .confirming : .intake
                messages.append(
                    AIConversationMessage(
                        role: .assistant,
                        text: reopened.assistantMessage
                    )
                )
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
        let normalized = text.lowercased()
        return ["yes", "y", "confirm", "confirmed", "looks good", "sounds good", "go ahead"].contains(normalized)
    }

    @ViewBuilder
    private func bubble(_ message: AIConversationMessage) -> some View {
        HStack {
            if message.role == .user { Spacer(minLength: 40) }
            Text(message.text)
                .font(.subheadline)
                .foregroundColor(message.role == .user ? Theme.white : Theme.primary)
                .padding(12)
                .background(message.role == .user ? Theme.primary : Theme.white)
                .cornerRadius(16)
                .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
                .frame(maxWidth: 300, alignment: message.role == .user ? .trailing : .leading)
            if message.role == .assistant { Spacer(minLength: 40) }
        }
    }

    private func confirmationCard(summary: String) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 14) {
                Text("Ready to Generate?")
                    .font(.headline)
                    .foregroundColor(Theme.primary)

                Text("If the summary above looks right, generate the plan. Otherwise, keep editing and tell me what to change.")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(spacing: 10) {
                    AppButton("Generate Plan", variant: .primary) {
                        generatePlanFromDraft()
                    }
                    .disabled(isBusy)
                    .opacity(isBusy ? 0.6 : 1)

                    AppButton("Keep Editing", variant: .secondary) {
                        phase = .intake
                        messages.append(
                            AIConversationMessage(
                                role: .assistant,
                                text: "Tell me what you’d like to change in the intake."
                            )
                        )
                    }
                }
            }
        }
    }

    private func previewCard(_ planPreview: AIPlanPreview) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 16) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Plan Preview")
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(Theme.textSecondary)

                        Text(planPreview.title)
                            .font(.title3)
                            .fontWeight(.bold)
                            .foregroundColor(Theme.primary)
                    }

                    Spacer()

                    Text(planPreview.category.displayName)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Theme.primary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Theme.sageLight)
                        .cornerRadius(999)
                }

                Text(planPreview.description)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)

                VStack(spacing: 10) {
                    previewDetailRow(title: "Suggested Time", value: formattedTime(planPreview.triggerValue))
                    previewDetailRow(title: "Frequency", value: planPreview.frequencySummary)
                    previewDetailRow(title: "Experience Level", value: draft.experienceLevel?.displayName ?? "Not set")
                }

                Divider()

                VStack(alignment: .leading, spacing: 10) {
                    Text("Suggested Progression")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(Theme.primary)

                    ForEach(planPreview.progressions.sorted { $0.week < $1.week }, id: \.week) { progression in
                        HStack(alignment: .top, spacing: 10) {
                            Text("Week \(progression.week)")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(Theme.primary)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(Theme.offWhite)
                                .cornerRadius(999)

                            Text(progression.description)
                                .font(.subheadline)
                                .foregroundColor(Theme.textSecondary)
                                .fixedSize(horizontal: false, vertical: true)

                            Spacer(minLength: 0)
                        }
                    }
                }

                VStack(spacing: 10) {
                    AppButton("Create Habit", variant: .primary) {
                        createHabit()
                    }
                    .disabled(isBusy)
                    .opacity(isBusy ? 0.6 : 1)

                    AppButton("Revise Plan", variant: .secondary) {
                        beginRevision()
                    }

                    AppButton("Start Over", variant: .secondary) {
                        restartConversation()
                    }
                }
            }
        }
    }

    private func successCard(createdHabitName: String) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(Theme.sage)

                    Text("Habit Created")
                        .font(.headline)
                        .foregroundColor(Theme.primary)
                }

                Text("\(createdHabitName) has been added to your habits.")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)

                AppButton("Generate Another Habit", variant: .secondary) {
                    restartConversation()
                }
            }
        }
    }

    private func loadingCard(title: String, message: String) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 10) {
                ProgressView()
                    .tint(Theme.primary)
                Text(title)
                    .font(.headline)
                    .foregroundColor(Theme.primary)
                Text(message)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func messageCard(title: String, text: String, icon: String, color: Color) -> some View {
        HabitCard {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: icon)
                    .font(.system(size: 22))
                    .foregroundColor(color)
                Text(title)
                    .font(.headline)
                    .foregroundColor(Theme.primary)
                Text(text)
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder
    private func previewDetailRow(title: String, value: String) -> some View {
        HStack(alignment: .top) {
            Text(title)
                .font(.subheadline)
                .foregroundColor(Theme.textSecondary)
            Spacer()
            Text(value)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundColor(Theme.primary)
                .multilineTextAlignment(.trailing)
        }
    }

    private func formattedTime(_ value: String) -> String {
        guard let date = BackendHabitMapper.time(from: value) else {
            return value
        }

        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

private struct AnimatedComposerPlaceholder: View {
    let text: String

    @State private var availableWidth: CGFloat = 0
    @State private var textWidth: CGFloat = 0
    @State private var animate = false

    private var targetOffset: CGFloat {
        min(0, availableWidth - textWidth)
    }

    var body: some View {
        GeometryReader { geometry in
            Text(text)
                .font(.body)
                .foregroundColor(Theme.textSecondary.opacity(0.75))
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
