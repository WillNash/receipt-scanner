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

  Future<void> signIn(String username, String password) async {
    state = const AuthLoading();
    try {
      final tokens = await _repo.signIn(username, password);
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
    await _repo.clearTokens();
    state = const Unauthenticated();
  }

  Future<String?> getIdToken() async {
    final current = state;
    if (current is! Authenticated) return null;

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
