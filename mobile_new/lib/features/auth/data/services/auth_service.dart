import 'package:flutter_appauth/flutter_appauth.dart';

import '../../../../core/config/app_config.dart';
import '../models/auth_tokens.dart';

class AuthService {
  AuthService() : _appAuth = const FlutterAppAuth();

  final FlutterAppAuth _appAuth;

  static final _serviceConfig = AuthorizationServiceConfiguration(
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
        preferEphemeralSession: true,
      ),
    );
    if (result == null) throw Exception('Sign-in cancelled');
    return _tokensFromAuthorization(result);
  }

  Future<AuthTokens?> refresh(AuthTokens current) async {
    final refreshToken = current.refreshToken;
    if (refreshToken == null) return null;

    try {
      final result = await _appAuth.token(
        TokenRequest(
          AppConfig.cognitoClientId,
          AppConfig.redirectUri,
          refreshToken: refreshToken,
          grantType: 'refresh_token',
          serviceConfiguration: _serviceConfig,
          scopes: AppConfig.scopes,
        ),
      );
      if (result == null) return null;
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

  Future<void> endSession(AuthTokens tokens) async {
    try {
      await _appAuth.endSession(
        EndSessionRequest(
          idTokenHint: tokens.idToken,
          postLogoutRedirectUrl: AppConfig.postLogoutRedirectUri,
          serviceConfiguration: _serviceConfig,
        ),
      );
    } catch (_) {
      // Best-effort — local tokens are cleared regardless
    }
  }

  AuthTokens _tokensFromAuthorization(AuthorizationTokenResponse result) {
    return AuthTokens(
      idToken: result.idToken ?? '',
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
      expiry: result.accessTokenExpirationDateTime,
    );
  }
}
