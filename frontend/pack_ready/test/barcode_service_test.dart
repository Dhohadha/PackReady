import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_exception.dart';
import 'package:packready/core/network/api_config.dart';
import 'package:packready/shared/services/api_barcode_repository.dart';

void main() {
  setUp(() {
    ApiConfig.baseUrl = 'http://testapi.local';
  });

  group('BarcodeRepository tests', () {
    test('Case 4 - Product + StoreProduct + Inventory exist', () async {
      final payload = {
        'product_found': true,
        'store_product_found': true,
        'inventory_found': true,
        'product': {
          'id': 'p001-uuid-string',
          'name': 'Kinder Joy Chocolate',
          'brand': 'Kinder',
          'category_id': null
        },
        'store_product': {
          'id': 'sp001-uuid-string',
          'selling_price': 45.0,
          'is_available': true,
          'marketplace_enabled': true
        },
        'inventory': {
          'id': 'inv001-uuid-string',
          'quantity': 15
        }
      };

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/stores/store_001/products/resolve');
        expect(request.url.queryParameters['identifier_type'], 'EAN');
        expect(request.url.queryParameters['value'], '8000500224163');
        return http.Response(jsonEncode(payload), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final repo = ApiBarcodeRepository(apiClient);

      final result = await repo.resolveBarcode(
        storeId: 'store_001',
        identifierType: 'EAN',
        value: '8000500224163',
      );

      expect(result.productFound, isTrue);
      expect(result.storeProductFound, isTrue);
      expect(result.inventoryFound, isTrue);
      expect(result.product?.name, 'Kinder Joy Chocolate');
      expect(result.storeProduct?.sellingPrice, 45.0);
      expect(result.inventory?.quantity, 15);
    });

    test('Case 3 - Product + StoreProduct mapped, no inventory', () async {
      final payload = {
        'product_found': true,
        'store_product_found': true,
        'inventory_found': false,
        'product': {
          'id': 'p002-uuid-string',
          'name': 'Colgate Toothpaste',
          'brand': 'Colgate',
          'category_id': null
        },
        'store_product': {
          'id': 'sp002-uuid-string',
          'selling_price': 120.0,
          'is_available': true,
          'marketplace_enabled': false
        },
        'inventory': null
      };

      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode(payload), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final repo = ApiBarcodeRepository(apiClient);

      final result = await repo.resolveBarcode(
        storeId: 'store_001',
        identifierType: 'EAN',
        value: '8901123000557',
      );

      expect(result.productFound, isTrue);
      expect(result.storeProductFound, isTrue);
      expect(result.inventoryFound, isFalse);
      expect(result.product?.name, 'Colgate Toothpaste');
      expect(result.storeProduct?.sellingPrice, 120.0);
      expect(result.inventory, isNull);
    });

    test('Case 2 - Product recognized, no StoreProduct', () async {
      final payload = {
        'product_found': true,
        'store_product_found': false,
        'inventory_found': false,
        'product': {
          'id': 'p003-uuid-string',
          'name': 'Dettol Handwash',
          'brand': 'Dettol',
          'category_id': null
        },
        'store_product': null,
        'inventory': null
      };

      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode(payload), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final repo = ApiBarcodeRepository(apiClient);

      final result = await repo.resolveBarcode(
        storeId: 'store_001',
        identifierType: 'EAN',
        value: '8901396328322',
      );

      expect(result.productFound, isTrue);
      expect(result.storeProductFound, isFalse);
      expect(result.inventoryFound, isFalse);
      expect(result.product?.name, 'Dettol Handwash');
      expect(result.storeProduct, isNull);
    });

    test('Case 1 - Unknown product throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response(jsonEncode({'detail': 'Product not found'}), 404);
      });

      final apiClient = ApiClient(client: mockClient);
      final repo = ApiBarcodeRepository(apiClient);

      expect(
        () => repo.resolveBarcode(
          storeId: 'store_001',
          identifierType: 'EAN',
          value: '9999999999999',
        ),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.notFound)),
      );
    });

    test('HTTP 500 throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Server Error', 500);
      });

      final apiClient = ApiClient(client: mockClient);
      final repo = ApiBarcodeRepository(apiClient);

      expect(
        () => repo.resolveBarcode(
          storeId: 'store_001',
          identifierType: 'EAN',
          value: '12345',
        ),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.serverError)),
      );
    });
  });
}
