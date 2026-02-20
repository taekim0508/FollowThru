import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var email = ""
    @State private var password = ""
    @State private var notificationsEnabled = false
    @State private var showDeleteConfirm = false

    var body: some View {
        Form {
            Section("Account") {
                HStack {
                    Label("Email", systemImage: "envelope")
                    Spacer()
                    TextField("Email", text: $email)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(Theme.textSecondary)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                }
                HStack {
                    Label("Password", systemImage: "lock")
                    Spacer()
                    SecureField("New password", text: $password)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(Theme.textSecondary)
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
            email = appState.currentUser?.email ?? ""
        }
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
        guard !email.isEmpty else { return }
        appState.currentUser?.email = email
        dismiss()
    }
}
