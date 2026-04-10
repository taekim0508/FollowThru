import SwiftUI

struct HabitDetailView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    let habit: Habit

    @State private var isEditing = false
    @State private var showDeleteAlert = false
    @State private var isLoading = false

    // editable fields
    @State private var name = ""
    @State private var description = ""
    @State private var habitType = ""
    @State private var targetValueString = ""
    @State private var quantityUnit = ""
    @State private var selectedPresetUnit = "minutes"
    @State private var showCustomUnit = false
    @State private var selectedDays: Set<String> = []
    @State private var showDayWarning = false
    @State private var triggerTime = Date()
    @State private var useReminderTime = false
    
    // Category and Motivation Statement
    @State private var selectedCategory = ""
    @State private var motivationStatement = ""

    private let categories = [
        "Fitness",
        "Health & Wellness",
        "Work",
        "Social",
        "Lifestyle",
        "Finance",
        "Creativity",
        "Other"
    ]
    private let presetUnits = ["times", "miles", "minutes"]
    private let dayNames = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    private let dayLabels = ["S", "M", "T", "W", "T", "F", "S"]

    private var effectiveUnit: String {
        showCustomUnit ? quantityUnit : selectedPresetUnit
    }

    private var canSave: Bool {
        guard !name.isEmpty else { return false }
        guard !selectedDays.isEmpty else { return false }
        if habitType == "tracked" {
            guard !targetValueString.isEmpty else { return false }
            guard Double(targetValueString) != nil else { return false }
            guard !effectiveUnit.isEmpty else { return false }
        }
        return true
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
                    categorySection
                    motivationSection
                    habitTypeSection
                    scheduleSection
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
                        if isEditing { cancelEdit() } else { dismiss() }
                    }
                    .foregroundColor(Theme.textSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    if isLoading {
                        ProgressView()
                    } else {
                        Button(isEditing ? "Save" : "Edit") {
                            if isEditing { save() }
                            else { withAnimation { isEditing = true } }
                        }
                        .fontWeight(.semibold)
                        .foregroundColor(isEditing && !canSave ? Theme.textSecondary : Theme.primary)
                        .disabled(isEditing && !canSave)
                    }
                }
            }
            .alert("Delete Habit", isPresented: $showDeleteAlert) {
                Button("Delete", role: .destructive) {
                    Task {
                        await appState.deleteHabit(habit)
                        dismiss()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will permanently delete \"\(habit.name)\" and all its history. This can't be undone.")
            }
            .onAppear { populateFields() }
        }
    }

    // MARK: - Stats Section

    private var statsSection: some View {
        HabitCard {
            HStack(spacing: 0) {
                statItem(
                    icon: "flame.fill",
                    color: Theme.terracotta,
                    value: "\(habit.currentStreak)",
                    label: "Streak"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: "trophy.fill",
                    color: Theme.sage,
                    value: "\(habit.maxStreak)",
                    label: "Best"
                )
                Divider().frame(height: 40)
                statItem(
                    icon: habit.todayComplete ? "checkmark.circle.fill" : "circle",
                    color: habit.todayComplete ? Theme.sage : Theme.textSecondary,
                    value: habit.todayComplete ? "Done" : "Pending",
                    label: "Today"
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

    // MARK: - Edit Sections

    private var nameSection: some View {
        fieldSection("Habit Name") {
            if isEditing {
                TextField("Habit name", text: $name)
                    .foregroundColor(Theme.primary)
                    .accentColor(Theme.primary)
                    .padding(12)
                    .background(Theme.white)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
            } else {
                readOnly(habit.name)
            }
        }
    }

    private var descriptionSection: some View {
        fieldSection("Description") {
            if isEditing {
                TextField("Description", text: $description)
                    .foregroundColor(Theme.primary)
                    .accentColor(Theme.primary)
                    .padding(12)
                    .background(Theme.white)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
            } else {
                readOnly(habit.description.isEmpty ? "None" : habit.description)
            }
        }
    }

    private var habitTypeSection: some View {
        fieldSection("Tracking") {
            // habit type is read-only — cannot be changed after creation
            let typeLabel = habit.habitType == "binary" ? "Completion" : "Numeric Goal"
            let unitLabel = habit.quantityUnit.map {
                " · \(habit.targetValue.map { "\(Int($0)) " } ?? "")\($0)"
            } ?? ""
            readOnly("\(typeLabel)\(unitLabel)")
        }
    }

    private var scheduleSection: some View {
        fieldSection("Repeat on") {
            if isEditing {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        ForEach(Array(dayNames.enumerated()), id: \.offset) { index, day in
                            let selected = selectedDays.contains(day)
                            Button { toggleDay(day) } label: {
                                Text(dayLabels[index])
                                    .font(.caption).fontWeight(.semibold)
                                    .frame(width: 36, height: 36)
                                    .background(selected ? Theme.primary : Theme.offWhite)
                                    .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                    .clipShape(Circle())
                            }
                        }
                    }
                    if showDayWarning {
                        Text("At least one day must be selected")
                            .font(.caption)
                            .foregroundColor(Theme.terracotta)
                    }
                }
            } else {
                let days = habit.frequencyPattern.days
                let display = days.count == 7
                    ? "Every day"
                    : days.map { $0.prefix(3).capitalized }.joined(separator: ", ")
                readOnly(display)
            }
        }
    }

    private var timeSection: some View {
        fieldSection("Reminder time") {
            if isEditing {
                Toggle("Set a reminder time", isOn: $useReminderTime)
                    .tint(Theme.primary)

                if useReminderTime {
                    DatePicker(
                        "Time",
                        selection: $triggerTime,
                        displayedComponents: .hourAndMinute
                    )
                    .datePickerStyle(.compact)
                    .labelsHidden()
                    .transition(.opacity)
                }
            } else {
                // show "No reminder" if trigger_value is placeholder "00:00"
                if let time = habit.triggerValue {
                    readOnly(time)
                } else {
                    readOnly("No reminder")
                }
            }
        }
        .animation(.easeInOut(duration: 0.2), value: useReminderTime)
    }

    private var deleteButton: some View {
        Button { showDeleteAlert = true } label: {
            HStack {
                Spacer()
                Image(systemName: "trash")
                Text("Delete Habit").fontWeight(.semibold)
                Spacer()
            }
            .foregroundColor(.red)
            .padding(14)
            .background(Color.red.opacity(0.08))
            .cornerRadius(12)
        }
        .padding(.top, 8)
    }
    
    private var categorySection: some View {
        fieldSection("Category") {
            if isEditing {
                LazyVGrid(
                    columns: [GridItem(.adaptive(minimum: 100), spacing: 8)],
                    alignment: .leading,
                    spacing: 8
                ) {
                    ForEach(categories, id: \.self) { category in
                        let selected = selectedCategory == category
                        Button {
                            selectedCategory = category
                        } label: {
                            Text(category)
                                .font(.subheadline).fontWeight(.medium)
                                .padding(.horizontal, 12).padding(.vertical, 8)
                                .frame(maxWidth: .infinity)
                                .background(selected ? Theme.primary : Theme.offWhite)
                                .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                .cornerRadius(20)
                        }
                    }
                }
            } else {
                readOnly(habit.category)
            }
        }
    }

    private var motivationSection: some View {
        fieldSection("Motivation") {
            if isEditing {
                TextField(
                    "Why do you want to build this habit?",
                    text: $motivationStatement,
                    axis: .vertical
                )
                .foregroundColor(Theme.primary)
                .accentColor(Theme.primary)
                .lineLimit(3...5)
                .padding(12)
                .background(Theme.white)
                .cornerRadius(10)
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
            } else {
                if let motivation = habit.motivationStatement, !motivation.isEmpty {
                    readOnly(motivation)
                } else {
                    readOnly("None")
                }
            }
        }
    }

    // MARK: - Helpers

    @ViewBuilder
    private func fieldSection<Content: View>(
        _ title: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline).fontWeight(.semibold)
                .foregroundColor(Theme.primary)
            content()
        }
    }

    @ViewBuilder
    private func readOnly(_ value: String) -> some View {
        Text(value)
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.offWhite)
            .cornerRadius(10)
            .foregroundColor(Theme.primary)
    }

    private func toggleDay(_ day: String) {
        if selectedDays.contains(day) {
            if selectedDays.count == 1 {
                showDayWarning = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    showDayWarning = false
                }
                return
            }
            selectedDays.remove(day)
        } else {
            selectedDays.insert(day)
        }
        showDayWarning = false
    }

    private func populateFields() {
        name = habit.name
        description = habit.description
        habitType = habit.habitType
        selectedCategory = habit.category
        motivationStatement = habit.motivationStatement ?? ""
        targetValueString = habit.targetValue.map { String(Int($0)) } ?? ""
        selectedDays = Set(habit.frequencyPattern.days)
        
        
        if let unit = habit.quantityUnit {
            if presetUnits.contains(unit) {
                selectedPresetUnit = unit
                showCustomUnit = false
            } else {
                quantityUnit = unit
                showCustomUnit = true
            }
        }
        
        // null trigger_value = no reminder
        useReminderTime = habit.triggerValue != nil
        if let tv = habit.triggerValue {
            let formatter = DateFormatter()
            formatter.dateFormat = "HH:mm"
            if let t = formatter.date(from: tv) {
                triggerTime = t
            }
        }
    }

    private func cancelEdit() {
        populateFields()
        withAnimation { isEditing = false }
    }

    private func save() {
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "HH:mm"

        // wrap trigger value — .null explicitly clears it, .value sets it
        let triggerNullable: Nullable<String>? = useReminderTime
            ? .value(timeFormatter.string(from: triggerTime))
            : .null

        let targetValue = habitType == "tracked" ? Double(targetValueString) : nil
        let unit = habitType == "tracked" ? effectiveUnit : nil

        isLoading = true
        Task {
            await appState.updateHabit(
                habit,
                name: name,
                description: description,
                triggerValue: triggerNullable,
                frequencyPattern: ["days": Array(selectedDays)],
                habitType: habitType,
                targetValue: targetValue,
                quantityUnit: unit,
                category: selectedCategory,
                motivationStatement: motivationStatement.isEmpty ? nil : motivationStatement
            )
            isLoading = false
            withAnimation { isEditing = false }
        }
    }
}
