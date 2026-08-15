import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_config.dart';
import 'package:packready/core/network/api_exception.dart';

void main() {
  setUp(() {
    ApiConfig.baseUrl = 'http://testapi.local';
  });

  group('ApiClient GET tests', () {
    test('Successful GET returns decoded JSON', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products');
        expect(request.url.queryParameters['limit'], '5');
        return http.Response(jsonEncode({'items': []}), 200);
      });

      final api = ApiClient(client: mockClient);
      final result = await api.get('/products', queryParameters: {'limit': '5'});
      expect(result, isMap);
      expect(result['items'], isEmpty);
    });

    test('400 Bad Request throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Bad request details', 400);
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.badRequest)),
      );
    });

    test('404 Not Found throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Not found', 404);
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.notFound)),
      );
    });

    test('422 Unprocessable throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Unprocessable Entity', 422);
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.unprocessable)),
      );
    });

    test('500 Server Error throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Server Error', 500);
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.serverError)),
      );
    });

    test('Invalid JSON response throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('not-a-json', 200);
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.invalidResponse)),
      );
    });

    test('Timeout throws ApiException', () async {
      final mockClient = MockClient((request) async {
        await Future.delayed(const Duration(milliseconds: 100));
        return http.Response('{}', 200);
      });

      final api = ApiClient(client: mockClient, timeout: const Duration(milliseconds: 10));
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.timeout)),
      );
    });

    test('Network failure throws ApiException', () async {
      final mockClient = MockClient((request) async {
        throw http.ClientException('No Internet');
      });

      final api = ApiClient(client: mockClient);
      expect(
        () => api.get('/products'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.networkFailure)),
      );
    });
  });

  group('ApiClient POST tests', () {
    test('Successful POST encodes request body and returns JSON', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products');
        expect(request.headers['Content-Type'], 'application/json');
        final Map<String, dynamic> body = jsonDecode(request.body);
        expect(body['name'], 'New Product');
        return http.Response(jsonEncode({'success': true}), 201);
      });

      final api = ApiClient(client: mockClient);
      final result = await api.post('/products', body: {'name': 'New Product'});
      expect(result, isMap);
      expect(result['success'], isTrue);
    });
  });
}
