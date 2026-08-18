// Fill these in from `terraform output` after running `make deploy`.
class AppConfig {
  AppConfig._();

  // terraform output api_invoke_url
  static const String apiBaseUrl =
      'https://REPLACE.execute-api.ap-southeast-2.amazonaws.com/v1';

  // terraform output cognito_client_id
  static const String cognitoClientId = 'REPLACE_CLIENT_ID';

  // terraform output cognito_base_url  (no trailing slash)
  static const String _cognitoBaseUrl =
      'https://bedrock-image-ai-025423.auth.ap-southeast-2.amazoncognito.com';

  static const String cognitoAuthEndpoint = '$_cognitoBaseUrl/oauth2/authorize';
  static const String cognitoTokenEndpoint = '$_cognitoBaseUrl/oauth2/token';
  static const String cognitoEndSessionEndpoint = '$_cognitoBaseUrl/logout';

  static const String redirectUri = 'com.willnash.receiptscanner://callback';
  static const String postLogoutRedirectUri =
      'com.willnash.receiptscanner://logout';

  static const List<String> scopes = ['email', 'openid', 'profile'];

  static const int maxFileSizeBytes = 20 * 1024 * 1024;
  static const int pollIntervalMs = 3000;
  static const int pollMaxAttempts = 60;
}
