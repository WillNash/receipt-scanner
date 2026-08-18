import 'package:flutter_appauth/flutter_appauth.dart';

import '../../../../core/config/app_config.dart';
import '../models/auth_tokens.dart';

class AuthService {
  const AuthService(this._appAuth);

  final FlutterAppAuth _appAuth;

  static const _serviceConfig = AuthorizationServiceConfiguration(
    authorizationEndpoint: AppConfig.cognitoAuthEndpoint,
    tokenEndpoint: AppConfig.cognitoTokenEndpoint,
    endSessionEndpoint: AppConfig.cognitoEndSessionEndpoint,
  );

  Future<AuthTokens> signIn() async {
    final result = await _appAuth.authorizeAndExchangeCode(
      AuthorizationTokenRequest(
        AppConfig.cognitoClientId,
        AppConfig.redirectUri,
        serviceConfiguration: _serviceConfig,
        scopes: AppConfig.scopes,
      ),
    );

    if (result?.idToken == null) {
      throw Exception('Sign in failed: no id_token received');
    }

    return AuthTokens(
      idToken: result!.idToken!,
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      expiry: result.accessTokenExpirationDateTime,
    );
  }

  Future<AuthTokens?> refresh(AuthTokens current) async {
    final refreshToken = current.refreshToken;
    if (refreshToken == null) return null;

    try {
      final result = await _appAuth.token(
        TokenRequest(
          AppConfig.cognitoClientId,
          AppConfig.redirectUri,
          serviceConfiguration: _serviceConfig,
          refreshToken: refreshToken,
          scopes: AppConfig.scopes,
        ),
      );

      if (result == null) return null;

      // Cognito returns a new id_token on refresh
      return AuthTokens(
        idToken: result.idToken ?? current.idToken,
        accessToken: result.accessToken,
        refreshToken: result.refreshToken ?? refreshToken,
        expiry: result.accessTokenExpirationDateTime,
      );
    } catch (_) {
      return null;
    }
  }
}
