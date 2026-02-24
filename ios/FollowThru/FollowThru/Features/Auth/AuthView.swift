import SwiftUI

struct AuthView: View {
    @EnvironmentObject var appState: AppState

    @State private var isSignUp = false
    @State private var username = ""
    @State private var email = ""
    @State private var password = ""

    private var canSubmit: Bool {
        !email.isEmpty && !password.isEmpty && (isSignUp ? !username.isEmpty : true) && !appState.isAuthLoading
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // Logo
            VStack(spacing: 8) {
                Circle()
                    .strokeBorder(Theme.sage, lineWidth: 3)
                    .frame(width: 72, height: 72)
                    .overlay(Image(systemName: "leaf.fill").foregroundColor(Theme.sage).font(.system(size: 28)))
                Text("FollowThru")
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundColor(Theme.primary)
            }
            .padding(.bottom, 36)

            // Toggle
            HStack(spacing: 0) {
                toggleTab("Sign In", selected: !isSignUp) { isSignUp = false }
                toggleTab("Sign Up", selected: isSignUp)  { isSignUp = true }
            }
            .background(Theme.offWhite)
            .cornerRadius(10)
            .padding(.horizontal)
            .padding(.bottom, 24)

            // Fields
            VStack(spacing: 14) {
                if isSignUp {
                    field("Username", text: $username, icon: "person")
                }
                field("Email", text: $email, icon: "envelope")
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                secureField("Password", text: $password, icon: "lock")
            }
            .padding(.horizontal)

            // Error
            if let error = appState.authError {
                Text(error)
                    .font(.footnote)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
                    .padding(.top, 8)
            }

            Spacer()

            // Action button
            AppButton(isSignUp ? "Create Account" : "Sign In", variant: .primary) {
                submit()
            }
            .disabled(!canSubmit)
            .padding(.horizontal)
            .padding(.bottom, 40)
        }
        .background(Theme.background.ignoresSafeArea())
    }

    // MARK: - Helpers

    private func submit() {
        Task {
            if isSignUp {
                await appState.register(email: email, password: password, username: username)
            } else {
                await appState.login(email: email, password: password)
            }
        }
    }

    @ViewBuilder
    private func field(_ placeholder: String, text: Binding<String>, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).foregroundColor(Theme.textSecondary).frame(width: 20)
            TextField(placeholder, text: text)
        }
        .padding(14)
        .background(Theme.white)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray, lineWidth: 1))
    }

    @ViewBuilder
    private func secureField(_ placeholder: String, text: Binding<String>, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).foregroundColor(Theme.textSecondary).frame(width: 20)
            SecureField(placeholder, text: text)
        }
        .padding(14)
        .background(Theme.white)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray, lineWidth: 1))
    }

    @ViewBuilder
    private func toggleTab(_ label: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.subheadline).fontWeight(.semibold)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(selected ? Theme.white : Color.clear)
                .foregroundColor(selected ? Theme.primary : Theme.textSecondary)
                .cornerRadius(8)
        }
        .padding(4)
    }
}
