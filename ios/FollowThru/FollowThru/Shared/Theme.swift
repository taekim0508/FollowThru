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
    // Mapped from tailwind HSL variables in index.css and converted to hex
    static let primary = Color(hex: "2B3D4F")    // deep navy
    static let softBlue = Color(hex: "8FA4B7")   // light blue backgrounds
    static let terracotta = Color(hex: "C57553") // accent/warning
    static let sage = Color(hex: "70957C")      // sage green
    static let sageLight = Color(hex: "F3F6F4") // very light sage
    static let beige = Color(hex: "F5F1EB")     // warm beige
    static let offWhite = Color(hex: "FBFAF9")  // off-white
    static let lightGray = Color(hex: "E8E8E8") // neutral light gray
    
    // Added tokens
    static let textSecondary = Color(hex: "65758B") // slate gray (approx of hsl(215,16%,47%))
    static let background = Theme.offWhite
    static let cardBackground = Theme.beige

    // Convenience tokens
    static let white = Color.white
    static let shadow = Color.black.opacity(0.08)
}
