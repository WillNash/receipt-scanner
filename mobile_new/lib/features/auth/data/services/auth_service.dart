import 'package:amazon_cognito_identity_dart_2/cognito.dart';

import '../../../../core/config/app_config.dart';
import '../models/auth_tokens.dart';

class AuthService {
  AuthService()
      : _pool = CognitoUserPool(
          AppConfig.cognitoUserPoolId,
          AppConfig.cognitoClientId,
        );

  final CognitoUserPool _pool;
  CognitoUser? _user;

  Future<AuthTokens> signIn(String email, String password) async {
    final user = CognitoUser(email, _pool);
    final session = await user.authenticateUser(
      AuthenticationDetails(username: email, password: password),
    );
    if (session == null) throw Exception('Sign-in failed');
    _user = user;
    return _tokensFromSession(session);
  }

  Future<AuthTokens?> refresh(AuthTokens current, String? username) async {
    if (current.refreshToken == null) return null;
    try {
      final user = _user ?? CognitoUser(username ?? '', _pool);
      final session = await user.refreshSession(
        CognitoRefreshToken(current.refreshToken!),
      );
      if (session == null) return null;
      _user = user;
      return AuthTokens(
        idToken: session.idToken.jwtToken ?? current.idToken,
        accessToken: session.accessToken.jwtToken,
        refreshToken: session.refreshToken?.token ?? current.refreshToken,
        expiry: DateTime.fromMillisecondsSinceEpoch(
          session.accessToken.getExpiration() * 1000,
        ),
      );
    } catch (_) {
      return null;
    }
  }

  Future<void> signOut() async {
    await _user?.signOut();
    _user = null;
  }

  AuthTokens _tokensFromSession(CognitoUserSession session) {
    return AuthTokens(
      idToken: session.idToken.jwtToken ?? '',
      accessToken: session.accessToken.jwtToken,
      refreshToken: session.refreshToken?.token,
      expiry: DateTime.fromMillisecondsSinceEpoch(
        session.accessToken.getExpiration() * 1000,
      ),
    );
  }
}
