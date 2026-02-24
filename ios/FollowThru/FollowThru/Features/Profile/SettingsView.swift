import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var email = ""
    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var notificationsEnabled = false
    @State private var showDeleteConfirm = false

    private var hasAccountChanges: Bool {
        let user = appState.currentUser
        let nameChanged = !name.isEmpty && name != (user?.username ?? "")
        let emailChanged = !email.isEmpty && email != (user?.email ?? "")
        let passwordChangeRequested = !newPassword.isEmpty
        return nameChanged || emailChanged || passwordChangeRequested
    }

    var body: some View {
        Form {
            Section("Account") {
                HStack {
                    Label("Name", systemImage: "person")
                    Spacer()
                    TextField("Name", text: $name)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(Theme.textSecondary)
                }
                HStack {
                    Label("Email", systemImage: "envelope")
                    Spacer()
                    TextField("Email", text: $email)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(Theme.textSecondary)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                }
                SecureField("Current password", text: $currentPassword)
                    .textContentType(.password)
                SecureField("New password", text: $newPassword)
                    .textContentType(.newPassword)
                if let error = appState.authError {
                    Text(error)
                        .font(.footnote)
                        .foregroundColor(.red)
                }
            }

            Section("Preferences") {
                Toggle(isOn: $notificationsEnabled) {
                    Label("Notifications", systemImage: "bell")
                }
                .tint(Theme.primary)
            }

            Section {
                Button("Save Changes") { saveChanges() }
                    .foregroundColor(Theme.primary)
                    .fontWeight(.semibold)
                    .disabled(!hasAccountChanges || appState.isAuthLoading)
                if appState.isAuthLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity)
                }
            }

            Section {
                Button("Delete Account", role: .destructive) {
                    showDeleteConfirm = true
                }
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            name = appState.currentUser?.username ?? ""
            email = appState.currentUser?.email ?? ""
            appState.authError = nil
        }
        .onChange(of: name) { _, _ in appState.authError = nil }
        .onChange(of: email) { _, _ in appState.authError = nil }
        .onChange(of: currentPassword) { _, _ in appState.authError = nil }
        .onChange(of: newPassword) { _, _ in appState.authError = nil }
        .confirmationDialog(
            "Delete your account?",
            isPresented: $showDeleteConfirm,
            titleVisibility: .visible
        ) {
            Button("Delete Account", role: .destructive) {
                appState.logout()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This action cannot be undone.")
        }
    }

    private func saveChanges() {
        guard hasAccountChanges else { return }

        let user = appState.currentUser
        let nameToSend: String? = (!name.isEmpty && name != (user?.username ?? "")) ? name : nil
        let emailToSend: String? = (!email.isEmpty && email != (user?.email ?? "")) ? email : nil
        let currentToSend: String? = !newPassword.isEmpty ? (currentPassword.isEmpty ? "" : currentPassword) : nil
        let newToSend: String? = !newPassword.isEmpty ? newPassword : nil

        if newToSend != nil && (currentToSend == nil || currentToSend?.isEmpty == true) {
            appState.authError = "Current password is required to set a new password."
            return
        }

        Task {
            await appState.updateAccount(
                name: nameToSend,
                email: emailToSend,
                currentPassword: currentToSend?.isEmpty == true ? nil : currentToSend,
                newPassword: newToSend
            )
            if appState.authError == nil {
                currentPassword = ""
                newPassword = ""
            }
        }
    }
}
