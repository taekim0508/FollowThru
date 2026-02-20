import SwiftUI

struct AppButton: View {
    enum Variant { case primary, secondary, compact }
    enum ColorStyle { case action, muted, success }

    let title: String
    let variant: Variant
    let colorStyle: ColorStyle?
    let action: () -> Void

    @State private var pressed = false

    init(_ title: String, variant: Variant = .primary, colorStyle: ColorStyle? = nil, action: @escaping () -> Void) {
        self.title = title
        self.variant = variant
        self.colorStyle = colorStyle
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            content
        }
        .scaleEffect(pressed ? 0.98 : 1.0)
        .simultaneousGesture(DragGesture(minimumDistance: 0)
            .onChanged({ _ in withAnimation(.spring(response: 0.2, dampingFraction: 0.6)) { pressed = true } })
            .onEnded({ _ in withAnimation(.spring()) { pressed = false } })
        )
    }

    @ViewBuilder
    private var content: some View {
        switch variant {
        case .primary:
            Text(title)
                .font(.system(size: 17, weight: .semibold))
                .foregroundColor(Theme.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(Theme.primary)
                .cornerRadius(12)

        case .secondary:
            Text(title)
                .font(.system(size: 17, weight: .semibold))
                .foregroundColor(Theme.primary)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(Theme.white)
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.primary, lineWidth: 1.5))
                .cornerRadius(12)

        case .compact:
            let (bg, fg) = compactColors()
            Text(title)
                .font(.subheadline).fontWeight(.semibold)
                .foregroundColor(fg)
                .padding(.horizontal, 14)
                .frame(minWidth: 120)
                .frame(height: 36)
                .background(bg)
                .cornerRadius(10)
                .fixedSize()
        }
    }

    private func compactColors() -> (Color, Color) {
        switch colorStyle {
        case .action:
            return (Theme.primary, Theme.white)
        case .muted:
            return (Theme.offWhite, Theme.textSecondary)
        case .success:
            return (Theme.sage, Theme.white)
        case .none:
            return (Theme.softBlue, Theme.white)
        }
    }
}

struct HabitCard<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        VStack { content }
            .padding(16)
            .background(Theme.white)
            .cornerRadius(16)
            .shadow(color: Theme.shadow, radius: 8, x: 0, y: 2)
    }
}

struct HabitProgressBar: View {
    var value: Double

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Theme.offWhite)
                    .frame(height: 4)

                RoundedRectangle(cornerRadius: 2)
                    .fill(Theme.primary)
                    .frame(width: max(0, geo.size.width * CGFloat(min(max(value, 0), 1))), height: 4)
                    .animation(.easeInOut, value: value)
            }
        }
        .frame(height: 4)
    }
}

// Previews
struct UIComponents_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 16) {
            AppButton("Primary", variant: .primary) {}
            AppButton("Secondary", variant: .secondary) {}
            HabitCard {
                Text("Habit card content")
            }
            HabitProgressBar(value: 0.6).frame(height: 8).padding()
        }
        .padding()
        .background(Theme.background)
    }
}

// Back navigation button
struct NavBackButton: View {
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            Image(systemName: "chevron.left")
                .font(.system(size: 17, weight: .semibold))
                .foregroundColor(Theme.primary)
                .frame(width: 36, height: 36)
                .background(Theme.white)
                .clipShape(Circle())
                .shadow(color: Theme.shadow, radius: 4, x: 0, y: 1)
        }
    }
}

// Tab bar button
struct TabBarButton: View {
    let icon: String
    let label: String
    let isActive: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 3) {
                Image(systemName: icon)
                    .font(.system(size: 20))
                Text(label)
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundColor(isActive ? Theme.primary : Theme.textSecondary)
        }
    }
}
