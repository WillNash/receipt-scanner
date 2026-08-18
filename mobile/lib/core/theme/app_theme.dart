import 'package:flutter/material.dart';

final appTheme = ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xFF1A73E8),
    brightness: Brightness.light,
  ),
  cardTheme: const CardThemeData(
    elevation: 2,
    margin: EdgeInsets.symmetric(horizontal: 16, vertical: 6),
  ),
  appBarTheme: const AppBarTheme(
    centerTitle: false,
    elevation: 0,
  ),
);
