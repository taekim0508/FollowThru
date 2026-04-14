import SwiftUI

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

struct Theme {
    // MARK: – Brand / Interactive
    // Used for: primary buttons, user chat bubbles, active tab icons, links
    static let primary      = Color(hex: "445E3E")  // dark sage green

    // MARK: – Sage Scale
    // Used for: icons, streaks, progress fills, checkmarks, accents
    static let sage         = Color(hex: "6B9462")  // medium sage
    static let sageLight    = Color(hex: "E6EDE4")  // very light sage tint (icon backgrounds, tags)

    // MARK: – Backgrounds & Surfaces
    static let background   = Color(hex: "F7F5F0")  // warm cream page background
    static let offWhite     = Color(hex: "F7F5F0")  // alias kept for legacy callsites
    static let cardBeige    = Color(hex: "EDEAE3")  // warm beige (category cards, AI assistant bubbles)
    static let beige        = Color(hex: "EDEAE3")  // alias
    static let cardBackground = Color(hex: "EDEAE3")

    // MARK: – Text
    // primary (above) doubles as the primary text color (dark sage reads as near-black charcoal)
    static let textSecondary = Color(hex: "6B7267")  // body / secondary text
    static let textTertiary  = Color(hex: "9AA396")  // section labels, timestamps, captions

    // MARK: – Borders & Dividers
    static let lightGray    = Color(hex: "E2DDD6")  // warm gray border / divider
    static let border       = Color(hex: "E2DDD6")  // alias

    // MARK: – Feedback
    static let terracotta   = Color(hex: "C57553")  // warning / error
    static let success      = Color(hex: "5B8655")  // success green (same family as sage)

    // MARK: – Utility
    static let white        = Color.white
    static let shadow       = Color.black.opacity(0.06)

    // MARK: – Legacy aliases (kept so unchanged views compile without edits)
    static let softBlue     = Color(hex: "E6EDE4")  // remapped to sageLight

    // MARK: – Category chip styles
    /// Returns (background, foreground) for a given habit category name.
    static func categoryChipStyle(_ category: String) -> (background: Color, foreground: Color) {
        switch category {
        case "Fitness":           return (Color(hex: "FAE8E0"), Color(hex: "C75A2A"))
        case "Health & Wellness": return (Color(hex: "E6EDE4"), Color(hex: "6B9462"))
        case "Work":              return (Color(hex: "E3E8F0"), Color(hex: "4A6FA5"))
        case "Social":            return (Color(hex: "EDE8F5"), Color(hex: "7B5EA7"))
        case "Lifestyle":         return (Color(hex: "FBF3DC"), Color(hex: "A0802A"))
        case "Finance":           return (Color(hex: "E0F0EE"), Color(hex: "3D8C85"))
        case "Creativity":        return (Color(hex: "FAE8EF"), Color(hex: "B5547A"))
        default:                  return (Color(hex: "EDEDEC"), Color(hex: "6B7267"))
        }
    }
}
