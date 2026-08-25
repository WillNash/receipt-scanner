import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../data/models/auth_tokens.dart';
import '../../data/repositories/auth_repository.dart';
import '../../data/services/auth_service.dart';

// ---------------------------------------------------------------------------
// Providers
// ---------------------------------------------------------------------------

final _secureStorageProvider = Provider<FlutterSecureStorage>(
  (_) => const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  ),
);

final _authServiceProvider = Provider<AuthService>(
  (_) => AuthService(),
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    ref.watch(_authServiceProvider),
    ref.watch(_secureStorageProvider),
  ),
);

final authProvider = NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

sealed class AuthState {
  const AuthState();
}

class AuthLoading extends AuthState {
  const AuthLoading();
}

class Unauthenticated extends AuthState {
  const Unauthenticated();
}

class Authenticated extends AuthState {
  const Authenticated({required this.tokens, this.email});

  final AuthTokens tokens;
  final String? email;
}

// ---------------------------------------------------------------------------
// Notifier
// ---------------------------------------------------------------------------

class AuthNotifier extends Notifier<AuthState> {
  // Non-null while a token refresh is in flight. Concurrent callers await the
  // same Future rather than each firing their own refresh against Cognito.
  Future<String?>? _refreshFuture;

  @override
  AuthState build() {
    Future.microtask(_init);
    return const AuthLoading();
  }

  AuthRepository get _repo => ref.read(authRepositoryProvider);

  Future<void> _init() async {
    final tokens = await _repo.loadTokens();
    if (tokens != null) {
      state = Authenticated(
        tokens: tokens,
        email: AuthRepository.extractEmail(tokens.idToken),
      );
    } else {
      state = const Unauthenticated();
    }
  }

  Future<void> signIn() async {
    state = const AuthLoading();
    try {
      final tokens = await _repo.signIn();
      state = Authenticated(
        tokens: tokens,
        email: AuthRepository.extractEmail(tokens.idToken),
      );
    } catch (e) {
      state = const Unauthenticated();
      rethrow;
    }
  }

  Future<void> signOut() async {
    final tokens = state is Authenticated ? (state as Authenticated).tokens : null;
    await _repo.signOut(tokens);
    state = const Unauthenticated();
  }

  Future<String?> getIdToken() async {
    final current = state;
    if (current is! Authenticated) return null;
    if (!current.tokens.isExpired) return current.tokens.idToken;

    _refreshFuture ??= _doRefresh(current)
        .whenComplete(() => _refreshFuture = null);
    return _refreshFuture;
  }

  Future<String?> _doRefresh(Authenticated current) async {
    final refreshed = await _repo.refreshIfNeeded(current.tokens);
    if (refreshed == null) {
      state = const Unauthenticated();
      return null;
    }
    if (!identical(refreshed, current.tokens)) {
      state = Authenticated(tokens: refreshed, email: current.email);
    }
    return refreshed.idToken;
  }
}
