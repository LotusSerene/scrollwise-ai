import 'package:flutter/material.dart';

class AppTheme {
  // Color constants
  static const Color _primaryDark = Color(0xFF2B2B2B);
  static const Color _secondaryDark = Color(0xFF3A3A3A);
  static const Color _primaryText = Color(0xFFE0E0E0);
  static const Color _accentBlue = Color(0xFF1F6FEB);
  static const Color _accentTeal = Color(0xFF00ADB5);
  static const Color _borderColor = Color(0xFF2C2C2C);
  static const Color _errorColor = Color(0xFFD9534F);
  static const Color _warningColor = Color(0xFFFFCC00);

  // Text Styles
  static const TextTheme _textTheme = TextTheme(
    displayLarge: TextStyle(
      fontSize: 32,
      fontWeight: FontWeight.bold,
      color: _primaryText,
    ),
    displayMedium: TextStyle(
      fontSize: 28,
      fontWeight: FontWeight.bold,
      color: _primaryText,
    ),
    bodyLarge: TextStyle(
      fontSize: 16,
      color: _primaryText,
    ),
    bodyMedium: TextStyle(
      fontSize: 14,
      color: _primaryText,
    ),
  );

  static final ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    primaryColor: _accentBlue,
    scaffoldBackgroundColor: _primaryDark,
    textTheme: _textTheme,

    // Card Theme
    cardTheme: CardTheme(
      color: _secondaryDark,
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _borderColor),
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
        fontWeight: FontWeight.bold,
      ),
    ),

    // Button Themes
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: _accentBlue,
        foregroundColor: _primaryText,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    ),

    // Input Decoration
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: _secondaryDark,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _accentBlue),
      ),
      labelStyle: const TextStyle(color: _primaryText),
    ),

    // Divider Theme
    dividerTheme: const DividerThemeData(
      color: _borderColor,
      thickness: 1,
    ),

    // Icon Theme
    iconTheme: const IconThemeData(
      color: _primaryText,
      size: 24,
    ),

    // Color Scheme
    colorScheme: const ColorScheme.dark(
      primary: _accentBlue,
      secondary: _accentTeal,
      error: _errorColor,
      errorContainer: _warningColor,
      surface: _secondaryDark,
      onPrimary: _primaryText,
      onSecondary: _primaryText,
      onSurface: _primaryText,
    ),
  );

  // You can add a light theme here if needed
  static final ThemeData lightTheme = ThemeData.light();
}
