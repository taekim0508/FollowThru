import SwiftUI

struct HabitDetailView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let habit: Habit

    @State private var isEditing = false
    @State private var showDeleteAlert = false

    // Editable fields
    @State private var name: String
    @State private var description: String
    @State private var kpiType: KPIType
    @State private var kpiTarget: String
    @State private var selectedDays: Set<Int>
    @State private var useTime: Bool
    @State private var scheduledTime: Date

    private let dayLabels = ["S","M","T","W","T","F","S"]
    private let cal = Calendar.current

    init(habit: Habit) {
        self.habit = habit
        _name = State(initialValue: habit.name)
        _description = State(initialValue: habit.description)
        _kpiType = State(initialValue: habit.kpiType)
        _kpiTarget = State(initialValue: habit.kpiTarget.map { String(Int($0)) } ?? "")
        _selectedDays = State(initialValue: Set(habit.scheduledDays))
        _useTime = State(initialValue: habit.scheduledTime != nil)
        _scheduledTime = State(initialValue: habit.scheduledTime ?? Date())
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {

                    if !isEditing {
                        statsSection
                    }

                    nameSection
                    descriptionSection
                    kpiSection
                    daysSection
                    timeSection

                    if isEditing {
                        deleteButton
                    }
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle(isEditing ? "Edit Habit" : habit.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(isEditing ? "Cancel" : "Close") {
                        if isEditing {
                            cancelEdit()
                        } else {
                            dismiss()
                        }
                    }
                    .foregroundColor(Theme.textSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(isEditing ? "Save" : "Edit") {
                        if isEditing {
                            save()
                        } else {
                            withAnimation { isEditing = true }
                        }
                    }
                    .fontWeight(.semibold)
                    .foregroundColor(Theme.primary)
                }
            }
            .alert("Delete Habit", isPresented: $showDeleteAlert) {
                Button("Delete", role: .destructive) {
                    appState.deleteHabit(habit)
                    dismiss()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will permanently delete \"\(habit.name)\" and all its history. This can't be undone.")
            }
        }
    }

    // MARK: - Stats Section

    private var statsSection: some View {
        HabitCard {
            HStack(spacing: 0) {
                statItem(
                    icon: "flame.fill",
                    color: Theme.terracotta,
                    value: "\(habit.streak)",
                    label: "Streak"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: "checkmark.circle.fill",
                    color: Theme.sage,
                    value: "\(totalCompletions)",
                    label: "Completions"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: "percent",
                    color: Theme.primary,
                    value: "\(completionRate)%",
                    label: "Rate"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: "calendar",
                    color: Theme.softBlue,
                    value: "\(daysSinceCreated)d",
                    label: "Age"
                )
            }
        }
    }

    @ViewBuilder
    private func statItem(icon: String, color: Color, value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Image(systemName: icon).foregroundColor(color)
            Text(value).font(.headline).foregroundColor(Theme.primary)
            Text(label).font(.caption).foregroundColor(Theme.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Editable Sections

    private var nameSection: some View {
        fieldSection("Habit Name") {
            if isEditing {
                TextField("Habit name", text: $name)
                    .padding(12)
                    .background(Theme.white)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
            } else {
                readOnlyRow(value: name)
            }
        }
    }

    private var descriptionSection: some View {
        fieldSection("Description") {
            if isEditing {
                TextField("What does this habit involve?", text: $description)
                    .padding(12)
                    .background(Theme.white)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
            } else {
                readOnlyRow(value: description.isEmpty ? "None" : description)
            }
        }
    }

    private var kpiSection: some View {
        fieldSection("Tracking") {
            if isEditing {
                Picker("KPI", selection: $kpiType) {
                    ForEach(KPIType.allCases, id: \.self) { t in
                        Text(t.rawValue).tag(t)
                    }
                }
                .pickerStyle(.segmented)

                if kpiType == .duration {
                    HStack {
                        TextField("e.g. 30", text: $kpiTarget)
                            .keyboardType(.numberPad)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                        Text("min")
                            .foregroundColor(Theme.textSecondary)
                            .fontWeight(.semibold)
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                } else if kpiType == .count {
                    HStack {
                        TextField("e.g. 10", text: $kpiTarget)
                            .keyboardType(.numberPad)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                        Text("times")
                            .foregroundColor(Theme.textSecondary)
                            .fontWeight(.semibold)
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            } else {
                let targetText = habit.kpiTarget.map { " · target: \(Int($0))" } ?? ""
                readOnlyRow(value: "\(habit.kpiType.rawValue)\(targetText)")
            }
        }
        .animation(.easeInOut(duration: 0.2), value: kpiType)
    }

    private var daysSection: some View {
        fieldSection("Repeat on") {
            if isEditing {
                HStack(spacing: 8) {
                    ForEach(1...7, id: \.self) { day in
                        let selected = selectedDays.contains(day)
                        Button { toggleDay(day) } label: {
                            Text(dayLabels[day - 1])
                                .font(.caption).fontWeight(.semibold)
                                .frame(width: 36, height: 36)
                                .background(selected ? Theme.primary : Theme.offWhite)
                                .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                .clipShape(Circle())
                        }
                    }
                }
            } else {
                readOnlyRow(value: scheduledDaysText)
            }
        }
    }

    private var timeSection: some View {
        fieldSection("Scheduled Time") {
            if isEditing {
                Toggle("Set a specific time", isOn: $useTime)
                    .tint(Theme.primary)
                if useTime {
                    DatePicker("Time", selection: $scheduledTime, displayedComponents: .hourAndMinute)
                        .datePickerStyle(.compact)
                        .labelsHidden()
                }
            } else {
                if let time = habit.scheduledTime {
                    readOnlyRow(value: time, formatter: timeFormatter)
                } else {
                    readOnlyRow(value: "No time set")
                }
            }
        }
    }

    private var deleteButton: some View {
        Button {
            showDeleteAlert = true
        } label: {
            HStack {
                Spacer()
                Image(systemName: "trash")
                Text("Delete Habit")
                    .fontWeight(.semibold)
                Spacer()
            }
            .foregroundColor(.red)
            .padding(14)
            .background(Color.red.opacity(0.08))
            .cornerRadius(12)
        }
        .padding(.top, 8)
    }

    // MARK: - Helpers

    @ViewBuilder
    private func fieldSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline).fontWeight(.semibold)
                .foregroundColor(Theme.primary)
            content()
        }
    }

    @ViewBuilder
    private func readOnlyRow(value: String) -> some View {
        Text(value)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.offWhite)
            .cornerRadius(10)
            .foregroundColor(Theme.primary)
    }

    @ViewBuilder
    private func readOnlyRow(value: Date, formatter: DateFormatter) -> some View {
        Text(formatter.string(from: value))
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.offWhite)
            .cornerRadius(10)
            .foregroundColor(Theme.primary)
    }

    private func toggleDay(_ day: Int) {
        if selectedDays.contains(day) { selectedDays.remove(day) }
        else { selectedDays.insert(day) }
    }

    private func save() {
        let targetValue: Double? = {
            switch kpiType {
            case .duration, .count: return Double(kpiTarget)
            case .checkbox: return nil
            }
        }()

        appState.updateHabit(habit, name: name, description: description, kpiType: kpiType, kpiTarget: targetValue, scheduledDays: Array(selectedDays).sorted(), scheduledTime: useTime ? scheduledTime : nil)

        withAnimation { isEditing = false }
    }

    private func cancelEdit() {
        // Reset all fields back to original
        name = habit.name
        description = habit.description
        kpiType = habit.kpiType
        kpiTarget = habit.kpiTarget.map { String(Int($0)) } ?? ""
        selectedDays = Set(habit.scheduledDays)
        useTime = habit.scheduledTime != nil
        scheduledTime = habit.scheduledTime ?? Date()
        withAnimation { isEditing = false }
    }

    // MARK: - Computed Stats

    private var totalCompletions: Int {
        appState.logs.filter { $0.habitId == habit.id && $0.completed }.count
    }

    private var completionRate: Int {
        let relevant = appState.logs.filter { $0.habitId == habit.id }
        guard !relevant.isEmpty else { return 0 }
        let completed = relevant.filter { $0.completed }.count
        return Int(Double(completed) / Double(relevant.count) * 100)
    }

    private var daysSinceCreated: Int {
        cal.dateComponents([.day], from: habit.createdAt, to: Date()).day ?? 0
    }

    private var scheduledDaysText: String {
        guard !habit.scheduledDays.isEmpty else { return "Every day" }
        let labels = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        return habit.scheduledDays.map { labels[$0 - 1] }.joined(separator: ", ")
    }
}

private let timeFormatter: DateFormatter = {
    let f = DateFormatter()
    f.timeStyle = .short
    return f
}()
