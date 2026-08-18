import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/presentation/view_models/auth_view_model.dart';

final apiClientProvider = Provider<Dio>((ref) {
  final dio = Dio(BaseOptions(
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 30),
  ));

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token =
            await ref.read(authProvider.notifier).getIdToken();
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) {
        // 401 means the token is invalid/expired and refresh failed — sign out.
        if (error.response?.statusCode == 401) {
          ref.read(authProvider.notifier).signOut();
        }
        handler.next(error);
      },
    ),
  );

  return dio;
});
