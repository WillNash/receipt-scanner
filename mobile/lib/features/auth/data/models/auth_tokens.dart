class AuthTokens {
  const AuthTokens({
    required this.idToken,
    this.accessToken,
    this.refreshToken,
    this.expiry,
  });

  final String idToken;
  final String? accessToken;
  final String? refreshToken;
  final DateTime? expiry;

  bool get isExpired {
    if (expiry == null) return false;
    return DateTime.now().isAfter(expiry!.subtract(const Duration(minutes: 5)));
  }
}
