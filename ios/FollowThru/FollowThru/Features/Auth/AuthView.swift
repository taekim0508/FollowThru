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
            Picker("", selection: $isSignUp) {
                Text("Sign In").tag(false)
                Text("Sign Up").tag(true)
            }
            .pickerStyle(.segmented)
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
            Image(systemName: icon).foregroundColor(Theme.primary).frame(width: 20)
            TextField("", text: text, prompt: Text(placeholder).foregroundColor(Theme.textSecondary))
                .foregroundColor(Theme.primary)
                .accentColor(Theme.primary)
        }
        .padding(14)
        .background(Theme.white)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray, lineWidth: 1))
    }

    @ViewBuilder
    private func secureField(_ placeholder: String, text: Binding<String>, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).foregroundColor(Theme.primary).frame(width: 20)
            SecureField("", text: text, prompt: Text(placeholder).foregroundColor(Theme.textSecondary))
                .foregroundColor(Theme.primary)
                .accentColor(Theme.primary)
        }
        .padding(14)
        .background(Theme.white)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.lightGray, lineWidth: 1))
    }

}
