import SwiftUI

struct CreateHabitView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""
    
    @State private var kpiType: KPIType = .checkbox
    @State private var kpiDurationTarget: String = ""
    @State private var kpiAmountTarget: String = ""
    
    @State private var selectedDays: Set<Int> = []   // 1=Sun…7=Sat
    @State private var useTime = false
    @State private var scheduledTime = Date()
    

    private let dayLabels = ["S","M","T","W","T","F","S"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {

                    // Name
                    fieldSection("Habit Name") {
                        TextField("e.g. Morning Run", text: $name)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                    }

                    // Description (optional)
                    fieldSection("Description (optional)") {
                        TextField("What does this habit involve?", text: $description)
                            .padding(12)
                            .background(Theme.white)
                            .cornerRadius(10)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.lightGray))
                    }

                    // KPI type
                    fieldSection("How will you track it?") {
                        Picker("KPI", selection: $kpiType) {
                            ForEach(KPIType.allCases, id: \.self) { t in
                                Text(t.rawValue).tag(t)
                            }
                        }
                        .pickerStyle(.segmented)

                        if kpiType == .duration {
                            HStack {
                                TextField("e.g. 30", text: $kpiDurationTarget)
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
                                TextField("e.g. 10", text: $kpiAmountTarget)
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
                    }

                    // Days of week
                    fieldSection("Repeat on") {
                        HStack(spacing: 8) {
                            ForEach(1...7, id: \.self) { day in
                                let selected = selectedDays.contains(day)
                                Button { toggle(day) } label: {
                                    Text(dayLabels[day - 1])
                                        .font(.caption).fontWeight(.semibold)
                                        .frame(width: 36, height: 36)
                                        .background(selected ? Theme.primary : Theme.offWhite)
                                        .foregroundColor(selected ? Theme.white : Theme.textSecondary)
                                        .clipShape(Circle())
                                }
                            }
                        }
                    }

                    // Optional time
                    fieldSection("Schedule a time?") {
                        Toggle("Set a specific time", isOn: $useTime)
                            .tint(Theme.primary)
                        if useTime {
                            DatePicker("Time", selection: $scheduledTime, displayedComponents: .hourAndMinute)
                                .datePickerStyle(.compact)
                                .labelsHidden()
                        }
                    }
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
                        .foregroundColor(name.isEmpty ? Theme.textSecondary : Theme.primary)
                        .disabled(name.isEmpty)
                }
            }
        }
    }

    // MARK: - Helpers

    private func toggle(_ day: Int) {
        if selectedDays.contains(day) { selectedDays.remove(day) }
        else { selectedDays.insert(day) }
    }

    private func save() {
        let targetValue: Double? = {
            switch kpiType {
            case .duration: return Double(kpiDurationTarget)
            case .count:    return Double(kpiAmountTarget)
            case .checkbox: return nil
            }
        }()

        let habit = Habit(
            name: name,
            description: description,
            kpiType: kpiType,
            kpiTarget: targetValue,
            scheduledDays: Array(selectedDays).sorted(),
            scheduledTime: useTime ? scheduledTime : nil
        )
        appState.habits.append(habit)
        dismiss()
    }

    @ViewBuilder
    private func fieldSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline).fontWeight(.semibold)
                .foregroundColor(Theme.primary)
            content()
        }
    }
}
