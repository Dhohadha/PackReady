import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_exception.dart';
import 'package:packready/shared/services/health_service.dart';

void main() {
  group('HealthService tests', () {
    test('Successful health check returns true', () async {
      final mockClient = MockClient((request) async {
        return http.Response('{"status": "ok", "service": "packready-api"}', 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final service = HealthService(apiClient);

      final result = await service.checkHealth();
      expect(result, isTrue);
    });

    test('Unhealthy status check returns false', () async {
      final mockClient = MockClient((request) async {
        return http.Response('{"status": "unhealthy"}', 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final service = HealthService(apiClient);

      final result = await service.checkHealth();
      expect(result, isFalse);
    });

    test('ApiException rethrows correctly', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Error', 500);
      });

      final apiClient = ApiClient(client: mockClient);
      final service = HealthService(apiClient);

      expect(
        () => service.checkHealth(),
        throwsA(isA<ApiException>()),
      );
    });
  });
}
