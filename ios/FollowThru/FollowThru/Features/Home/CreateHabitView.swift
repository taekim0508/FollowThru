import SwiftUI

struct CreateHabitView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""

    // habit type — "binary" or "tracked"
    @State private var habitType = "binary"

    // for tracked habits
    @State private var targetValueString = ""
    @State private var quantityUnit = ""
    @State private var showCustomUnit = false
    @State private var selectedPresetUnit = "minutes"

    // scheduling
    @State private var selectedDays: Set<String> = []
    @State private var showDayWarning = false
    @State private var useReminderTime = false

    // trigger time
    @State private var triggerTime = Date()
    
    // Categories and Motivation Statement
    @State private var selectedCategory = ""
    @State private var motivationStatement = ""

    // preset unit options
    private let presetUnits = ["times", "miles", "minutes"]
    private let dayNames = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    private let dayLabels = ["S", "M", "T", "W", "T", "F", "S"]
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

    private var canSave: Bool {
        guard !name.isEmpty else { return false }
        guard !selectedCategory.isEmpty else { return false }
        guard !selectedDays.isEmpty else { return false }
        if habitType == "tracked" {
            guard !targetValueString.isEmpty else { return false }
            guard Double(targetValueString) != nil else { return false }
            guard !effectiveUnit.isEmpty else { return false }
        }
        return true
    }

    private var effectiveUnit: String {
        showCustomUnit ? quantityUnit : selectedPresetUnit
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    // Name
                    fieldSection("Habit Name") {
                        TextField("e.g. Morning Run", text: $name)
                            .foregroundColor(Theme.primary)
                            .accentColor(Theme.primary)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                    }

                    // Description
                    fieldSection("Description (optional)") {
                        TextField("What does this habit involve?", text: $description)
                            .foregroundColor(Theme.primary)
                            .accentColor(Theme.primary)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                    }

                    // Habit Type
                    fieldSection("How will you track it?") {
                        Picker("Habit Type", selection: $habitType) {
                            Text("Completion-Based").tag("binary")
                            Text("Numeric Goal").tag("tracked")
                        }
                        .pickerStyle(.segmented)

                        if habitType == "tracked" {
                            VStack(alignment: .leading, spacing: 12) {
                                // target value
                                HStack {
                                    TextField("Target amount", text: $targetValueString)
                                        .keyboardType(.decimalPad)
                                        .foregroundColor(Theme.primary)
                                        .accentColor(Theme.primary)
                                        .padding(12)
                                        .background(Theme.white)
                                        .cornerRadius(10)
                                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))

                                    Text(effectiveUnit)
                                        .foregroundColor(Theme.textSecondary)
                                        .fontWeight(.semibold)
                                        .frame(minWidth: 60)
                                }

                                // unit picker
                                ScrollView(.horizontal, showsIndicators: false) {
                                    HStack(spacing: 8) {
                                        ForEach(presetUnits, id: \.self) { unit in
                                            Button {
                                                selectedPresetUnit = unit
                                                showCustomUnit = false
                                            } label: {
                                                Text(unit)
                                                    .font(.caption).fontWeight(.semibold)
                                                    .padding(.horizontal, 12).padding(.vertical, 6)
                                                    .background(
                                                        selectedPresetUnit == unit && !showCustomUnit
                                                        ? Theme.primary : Theme.offWhite
                                                    )
                                                    .foregroundColor(
                                                        selectedPresetUnit == unit && !showCustomUnit
                                                        ? Theme.white : Theme.textSecondary
                                                    )
                                                    .cornerRadius(16)
                                            }
                                        }

                                        // custom option
                                        Button {
                                            showCustomUnit = true
                                        } label: {
                                            Text("CUSTOM")
                                                .font(.caption).fontWeight(.semibold)
                                                .padding(.horizontal, 12).padding(.vertical, 6)
                                                .background(showCustomUnit ? Theme.primary : Theme.offWhite)
                                                .foregroundColor(showCustomUnit ? Theme.white : Theme.textSecondary)
                                                .cornerRadius(16)
                                        }
                                    }
                                }

                                if showCustomUnit {
                                    TextField("Enter custom unit", text: $quantityUnit)
                                        .foregroundColor(Theme.primary)
                                        .accentColor(Theme.primary)
                                        .padding(12)
                                        .background(Theme.white)
                                        .cornerRadius(10)
                                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                                        .transition(.opacity)
                                }
                            }
                            .transition(.opacity.combined(with: .move(edge: .top)))
                        }
                    }
                    .animation(.easeInOut(duration: 0.2), value: habitType)
                    
                    // Category — required
                    fieldSection("Category") {
                        // wrapping layout using FlowLayout-style with LazyVGrid
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
                    }

                    // Motivation Statement — optional
                    fieldSection("Motivation (optional)") {
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
                    }

                    // Schedule
                    fieldSection("Repeat on") {
                        HStack(spacing: 8) {
                            ForEach(Array(dayNames.enumerated()), id: \.offset) { index, day in
                                let selected = selectedDays.contains(day)
                                Button {
                                    toggleDay(day)
                                } label: {
                                    Text(dayLabels[index])
                                        .font(.caption).fontWeight(.semibold)
                                        .frame(width: 36, height: 36)
                                        .background(selected ? Theme.primary : Theme.offWhite)
                                        .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                        .clipShape(Circle())
                                }
                            }
                        }

                        // inline warning when trying to deselect last day
                        if showDayWarning {
                            Text("At least one day must be selected")
                                .font(.caption)
                                .foregroundColor(Theme.terracotta)
                                .transition(.opacity)
                        }
                    }

                    // Trigger time
                    fieldSection("Reminder time") {
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
                    }
                    .animation(.easeInOut(duration: 0.2), value: useReminderTime)
                }
                .padding()
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("New Habit")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundColor(Theme.textSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") { save() }
                        .fontWeight(.semibold)
                        .foregroundColor(canSave ? Theme.primary : Theme.textSecondary)
                        .disabled(!canSave)
                }
            }
            .onAppear {
                // auto-select today's weekday
                let formatter = DateFormatter()
                formatter.dateFormat = "EEEE"
                let today = formatter.string(from: Date()).lowercased()
                selectedDays.insert(today)
            }
        }
    }

    // MARK: - Helpers

    private func toggleDay(_ day: String) {
        if selectedDays.contains(day) {
            if selectedDays.count == 1 {
                // can't deselect last day — show warning
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

    private func save() {
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "HH:mm"
        // use "00:00" as placeholder when no reminder time set
        let triggerValueString: String? = useReminderTime ? timeFormatter.string(from: triggerTime) : nil
        let frequencyPattern = ["days": Array(selectedDays)]
        let targetValue = habitType == "tracked" ? Double(targetValueString) : nil
        let unit = habitType == "tracked" ? effectiveUnit : nil

        Task {
            await appState.createHabit(
                name: name,
                description: description,
                category: selectedCategory,
                habitType: habitType,
                targetValue: targetValue,
                quantityUnit: unit,
                triggerValue: triggerValueString,
                frequencyPattern: frequencyPattern,
                motivationStatement: motivationStatement.isEmpty ? nil : motivationStatement
            )
            dismiss()
        }
    }

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
}
