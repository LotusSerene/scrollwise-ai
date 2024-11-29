import 'package:flutter/material.dart';

class AppTheme {
  // Color constants
  static const Color _primaryDark = Color(0xFF1A1A1A);    // Lighter background
  static const Color _secondaryDark = Color(0xFF242424);   // Lighter secondary
  static const Color _primaryText = Color(0xFFFAFAFA);     // Crisp white text
  static const Color _secondaryText = Color(0xFFBBBBBB);   // Lighter gray text
  static const Color _accentBlue = Color(0xFF60A5FA);      // Keep modern blue accent
  static const Color _accentTeal = Color(0xFF2DD4BF);      // Keep fresh teal accent
  static const Color _borderColor = Color(0xFF323232);     // Lighter border
  static const Color _errorColor = Color(0xFFEF4444);      // Keep modern red
  static const Color _warningColor = Color(0xFFFBBF24);    // Keep modern yellow
  static const Color _surfaceColor = Color(0xFF202020);    // Lighter surface color
  // Text Styles
  static const TextTheme _textTheme = TextTheme(
    displayLarge: TextStyle(
      fontSize: 32,
      fontWeight: FontWeight.bold,
      color: _primaryText,
      letterSpacing: -1.0,
    ),
    displayMedium: TextStyle(
      fontSize: 28,
      fontWeight: FontWeight.bold,
      color: _primaryText,
      letterSpacing: -0.5,
    ),
    bodyLarge: TextStyle(
      fontSize: 16,
      color: _primaryText,
      letterSpacing: 0.1,
    ),
    bodyMedium: TextStyle(
      fontSize: 14,
      color: _secondaryText,
      letterSpacing: 0.1,
    ),
    labelLarge: TextStyle(
      fontSize: 14,
      fontWeight: FontWeight.w500,
      color: _primaryText,
      letterSpacing: 0.1,
    ),
  );

  static final ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    primaryColor: _accentBlue,
    scaffoldBackgroundColor: _primaryDark,
    textTheme: _textTheme,
    colorScheme: ColorScheme.dark(
      primary: _accentBlue,
      secondary: _accentTeal,
      surface: _surfaceColor,
      background: _primaryDark,
      error: _errorColor,
    ),

    // Card Theme
    cardTheme: CardTheme(
      color: _surfaceColor,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: _borderColor.withOpacity(0.5), width: 1),
      ),
    ),

    // AppBar Theme
    appBarTheme: const AppBarTheme(
      backgroundColor: _primaryDark,
      elevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        color: _primaryText,
        fontSize: 20,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.5,
      ),
    ),

    // Button Themes
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: _accentBlue,
        foregroundColor: _primaryText,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    ),

    // Input Decoration
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: _secondaryDark,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: _borderColor.withOpacity(0.3)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _accentBlue, width: 2),
      ),
      labelStyle: TextStyle(color: _primaryText.withOpacity(0.8)),
      hintStyle: TextStyle(color: _secondaryText.withOpacity(0.6)),
    ),

    // Divider Theme
    dividerTheme: DividerThemeData(
      color: _borderColor.withOpacity(0.3),
      thickness: 1,
    ),

    // Icon Theme
    iconTheme: IconThemeData(
      color: _primaryText.withOpacity(0.8),
      size: 24,
    ),
  );

  // You can add a light theme here if needed
  static final ThemeData lightTheme = ThemeData.light();
}
