import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_exception.dart';
import 'package:packready/core/network/api_config.dart';
import 'package:packready/shared/services/api_inventory_repository.dart';
import 'package:packready/shared/models/inventory_transaction.dart';

void main() {
  setUp(() {
    ApiConfig.baseUrl = 'http://testapi.local';
  });

  group('ApiInventoryRepository tests', () {
    test('getStore parses correctly', () async {
      final payload = {
        'id': 'store_001',
        'name': 'Sai Kirana Store',
        'status': 'ACTIVE',
        'created_at': '2026-08-13T10:00:00Z',
        'updated_at': '2026-08-13T10:00:00Z'
      };

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/stores/43a7a681-9235-46d1-82c8-65c697d5c022');
        return http.Response(jsonEncode(payload), 200);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      final store = await repo.getStore();

      expect(store.id, 'store_001');
      expect(store.name, 'Sai Kirana Store');
    });

    test('getProducts parses inventory and details', () async {
      final spListPayload = [
        {
          'id': 'sp001',
          'store_id': 'store_001',
          'product_id': 'p001',
          'selling_price': 40.0,
          'is_available': true,
          'marketplace_enabled': true,
          'created_at': '2026-08-13T10:00:00Z',
          'updated_at': '2026-08-13T10:00:00Z'
        }
      ];

      final productPayload = {
        'id': 'p001',
        'name': 'Milkybar Create 42g',
        'brand': 'Nestle',
        'category_id': 'cat001',
        'unit_value': 42.0,
        'unit_type': 'g'
      };

      final catPayload = {
        'id': 'cat001',
        'name': 'Chocolates',
        'parent_id': null
      };

      final identPayload = [
        {'id': 'id001', 'identifier_type': 'EAN', 'value': '8901058861921'}
      ];

      final invPayload = {
        'id': 'inv001',
        'store_product_id': 'sp001',
        'quantity': 20
      };

      final mockClient = MockClient((request) async {
        if (request.url.path == '/stores/43a7a681-9235-46d1-82c8-65c697d5c022/products') {
          return http.Response(jsonEncode(spListJson(spListPayload)), 200);
        } else if (request.url.path == '/products/p001') {
          return http.Response(jsonEncode(productPayload), 200);
        } else if (request.url.path == '/categories/cat001') {
          return http.Response(jsonEncode(catPayload), 200);
        } else if (request.url.path == '/products/p001/identifiers') {
          return http.Response(jsonEncode(identPayload), 200);
        } else if (request.url.path == '/inventory/sp001') {
          return http.Response(jsonEncode(invPayload), 200);
        }
        return http.Response('Not Found', 404);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      final products = await repo.getProducts();

      expect(products.length, 1);
      expect(products.first.id, 'sp001');
      expect(products.first.name, 'Milkybar Create 42g');
      expect(products.first.price, 40.0);
      expect(products.first.quantity, 20);
      expect(products.first.barcode, '8901058861921');
    });

    test('addStockToProduct stock-in request fields mapping', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/inventory/stock-in');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['store_product_id'], 'sp001');
        expect(body['quantity'], 5);
        expect(body['source'], 'MANUAL');
        return http.Response(jsonEncode({'id': 'inv001', 'store_product_id': 'sp001', 'quantity': 25}), 200);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      await repo.addStockToProduct('sp001', 5, TransactionSource.manual);
    });

    test('removeStockFromProduct stock-out request fields mapping', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/inventory/stock-out');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['store_product_id'], 'sp001');
        expect(body['quantity'], 2);
        expect(body['source'], 'BARCODE');
        return http.Response(jsonEncode({'id': 'inv001', 'store_product_id': 'sp001', 'quantity': 23}), 200);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      await repo.removeStockFromProduct('sp001', 2, TransactionSource.barcode);
    });

    test('Insufficient-stock throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode({'detail': 'Insufficient stock available'}), 400);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      expect(
        () => repo.removeStockFromProduct('sp001', 50, TransactionSource.manual),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.badRequest)),
      );
    });

    test('Invalid response throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Invalid JSON text', 200);
      });

      final repo = ApiInventoryRepository(ApiClient(client: mockClient));
      expect(
        () => repo.getStore(),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.invalidResponse)),
      );
    });
  });
}

dynamic spListJson(List<Map<String, dynamic>> items) {
  return items;
}
