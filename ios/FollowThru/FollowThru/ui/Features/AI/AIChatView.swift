import SwiftUI

struct AIChatView: View {
    @EnvironmentObject var appState: AppState
    @State private var input = ""
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: .assistant, text: "Hi! I'm your HabitFlow AI. Tell me about a habit you want to build and I'll help you create a plan.")
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(messages) { msg in
                                bubble(msg)
                            }
                        }
                        .padding()
                    }
                    .onChange(of: messages.count) { _ in
                        withAnimation { proxy.scrollTo(messages.last?.id, anchor: .bottom) }
                    }
                }

                Divider()

                HStack(spacing: 10) {
                    TextField("Ask about your habits…", text: $input)
                        .padding(12)
                        .background(Theme.offWhite)
                        .cornerRadius(20)

                    Button { send() } label: {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 32))
                            .foregroundColor(input.isEmpty ? Theme.lightGray : Theme.primary)
                    }
                    .disabled(input.isEmpty)
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(Theme.white)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("AI Coach")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func send() {
        let userMsg = ChatMessage(role: .user, text: input)
        messages.append(userMsg)
        input = ""

        // Stub response — replace with real API call later
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            let reply = ChatMessage(role: .assistant, text: "Great goal! I'll help you build a plan around that. What time of day works best for you?")
            messages.append(reply)
        }
    }

    @ViewBuilder
    private func bubble(_ msg: ChatMessage) -> some View {
        HStack {
            if msg.role == .user { Spacer() }
            Text(msg.text)
                .padding(12)
                .background(msg.role == .user ? Theme.primary : Theme.white)
                .foregroundColor(msg.role == .user ? Theme.white : Theme.primary)
                .cornerRadius(16)
                .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
                .frame(maxWidth: 280, alignment: msg.role == .user ? .trailing : .leading)
            if msg.role == .assistant { Spacer() }
        }
        .id(msg.id)
    }
}

struct ChatMessage: Identifiable {
    enum Role { case user, assistant }
    var id = UUID()
    var role: Role
    var text: String
}
