import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../../core/config/app_config.dart';
import '../models/auth_tokens.dart';

class AuthService {
  AuthService() : _dio = Dio();

  final Dio _dio;

  static const _cognitoEndpoint =
      'https://cognito-idp.ap-southeast-2.amazonaws.com/';

  static const _headers = {
    'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
    'Content-Type': 'application/x-amz-json-1.1',
  };

  Future<AuthTokens> signIn(String username, String password) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        _cognitoEndpoint,
        data: jsonEncode({
          'AuthFlow': 'USER_PASSWORD_AUTH',
          'ClientId': AppConfig.cognitoClientId,
          'AuthParameters': {
            'USERNAME': username,
            'PASSWORD': password,
          },
        }),
        options: Options(headers: _headers),
      );
      return _tokensFromResult(response.data!);
    } on DioException catch (e) {
      throw Exception('Cognito error: ${e.response?.data}');
    }
  }

  Future<AuthTokens?> refresh(AuthTokens current) async {
    final refreshToken = current.refreshToken;
    if (refreshToken == null) return null;

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        _cognitoEndpoint,
        data: jsonEncode({
          'AuthFlow': 'REFRESH_TOKEN_AUTH',
          'ClientId': AppConfig.cognitoClientId,
          'AuthParameters': {'REFRESH_TOKEN': refreshToken},
        }),
        options: Options(headers: _headers),
      );

      final tokens = _tokensFromResult(response.data!);
      // Cognito does not return a new refresh token on refresh
      return AuthTokens(
        idToken: tokens.idToken,
        accessToken: tokens.accessToken,
        refreshToken: refreshToken,
        expiry: tokens.expiry,
      );
    } catch (_) {
      return null;
    }
  }

  AuthTokens _tokensFromResult(Map<String, dynamic> body) {
    final result = body['AuthenticationResult'] as Map<String, dynamic>;
    return AuthTokens(
      idToken: result['IdToken'] as String,
      accessToken: result['AccessToken'] as String?,
      refreshToken: result['RefreshToken'] as String?,
      expiry: DateTime.now()
          .add(Duration(seconds: result['ExpiresIn'] as int? ?? 3600)),
    );
  }
}
