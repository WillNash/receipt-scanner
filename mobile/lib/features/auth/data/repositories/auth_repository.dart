import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../models/auth_tokens.dart';
import '../services/auth_service.dart';

class AuthRepository {
  const AuthRepository(this._service, this._storage);

  final AuthService _service;
  final FlutterSecureStorage _storage;

  static const _keyIdToken = 'id_token';
  static const _keyAccessToken = 'access_token';
  static const _keyRefreshToken = 'refresh_token';
  static const _keyExpiry = 'expiry';

  Future<AuthTokens> signIn() async {
    final tokens = await _service.signIn();
    await _store(tokens);
    return tokens;
  }

  Future<AuthTokens?> loadTokens() async {
    final idToken = await _storage.read(key: _keyIdToken);
    if (idToken == null) return null;

    final refreshToken = await _storage.read(key: _keyRefreshToken);
    final accessToken = await _storage.read(key: _keyAccessToken);
    final expiryStr = await _storage.read(key: _keyExpiry);
    final expiry = expiryStr != null ? DateTime.tryParse(expiryStr) : null;

    var tokens = AuthTokens(
      idToken: idToken,
      accessToken: accessToken,
      refreshToken: refreshToken,
      expiry: expiry,
    );

    if (tokens.isExpired) {
      final refreshed = await _service.refresh(tokens);
      if (refreshed != null) {
        await _store(refreshed);
        return refreshed;
      }
      await clearTokens();
      return null;
    }

    return tokens;
  }

  Future<AuthTokens?> refreshIfNeeded(AuthTokens current) async {
    if (!current.isExpired) return current;
    final refreshed = await _service.refresh(current);
    if (refreshed != null) await _store(refreshed);
    return refreshed;
  }

  Future<void> clearTokens() async {
    await _storage.deleteAll();
  }

  Future<void> _store(AuthTokens tokens) async {
    await _storage.write(key: _keyIdToken, value: tokens.idToken);
    if (tokens.accessToken != null) {
      await _storage.write(key: _keyAccessToken, value: tokens.accessToken);
    }
    if (tokens.refreshToken != null) {
      await _storage.write(key: _keyRefreshToken, value: tokens.refreshToken);
    }
    if (tokens.expiry != null) {
      await _storage.write(
          key: _keyExpiry, value: tokens.expiry!.toIso8601String());
    }
  }

  // Decode the email claim from the id_token JWT payload (no signature verification needed here —
  // the API Lambda validates the token on every request).
  static String? extractEmail(String idToken) {
    try {
      final parts = idToken.split('.');
      if (parts.length != 3) return null;
      final payload = base64Url.normalize(parts[1]);
      final decoded = utf8.decode(base64Url.decode(payload));
      final map = jsonDecode(decoded) as Map<String, dynamic>;
      return map['email'] as String?;
    } catch (_) {
      return null;
    }
  }
}
