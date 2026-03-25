//
//  InsightsView.swift
//  FollowThru
//
//  Created by Ronnie Yalung on 3/25/26.
//

import SwiftUI

struct InsightsView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: 14) {
                Spacer()
                Image(systemName: "chart.xyaxis.line")
                    .font(.system(size: 52))
                    .foregroundColor(Theme.softBlue)
                Text("Progress")
                    .font(.title2).bold()
                    .foregroundColor(Theme.primary)
                Text("Analytics and insights coming soon")
                    .font(.subheadline)
                    .foregroundColor(Theme.textSecondary)
                Spacer()
            }
            .frame(maxWidth: .infinity)
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Progress")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
