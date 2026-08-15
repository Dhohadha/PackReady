import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_exception.dart';
import 'package:packready/core/network/api_config.dart';
import 'package:packready/shared/services/api_product_repository.dart';

void main() {
  setUp(() {
    ApiConfig.baseUrl = 'http://testapi.local';
  });

  group('ApiProductRepository tests', () {
    test('createProduct parses id correctly', () async {
      final payload = {
        'id': 'prod_999-uuid-string',
        'name': 'Cadbury Silk',
        'brand': 'Cadbury',
        'description': null,
        'unit_value': null,
        'unit_type': 'pcs',
        'status': 'ACTIVE',
        'created_at': '2026-08-13T10:00:00Z',
        'updated_at': '2026-08-13T10:00:00Z'
      };

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['name'], 'Cadbury Silk');
        expect(body['brand'], 'Cadbury');
        return http.Response(jsonEncode(payload), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final productId = await repo.createProduct(
        name: 'Cadbury Silk',
        brand: 'Cadbury',
      );

      expect(productId, 'prod_999-uuid-string');
    });

    test('addIdentifier makes POST to identifiers endpoint', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_999-uuid-string/identifiers');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['identifier_type'], 'EAN');
        expect(body['value'], '8901234567890');
        return http.Response(jsonEncode({'id': 'ident_111'}), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      await repo.addIdentifier(
        productId: 'prod_999-uuid-string',
        identifierType: 'EAN',
        value: '8901234567890',
      );
    });

    test('addProductToStore resolves store product mapping id', () async {
      final payload = {
        'id': 'sp_888-uuid-string',
        'store_id': 'store_001',
        'product_id': 'prod_999',
        'selling_price': 80.0,
        'is_available': true,
        'marketplace_enabled': false,
        'created_at': '2026-08-13T10:00:00Z',
        'updated_at': '2026-08-13T10:00:00Z'
      };

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/stores/store_001/products');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['product_id'], 'prod_999');
        expect(body['selling_price'], 80.0);
        return http.Response(jsonEncode(payload), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final storeProductId = await repo.addProductToStore(
        storeId: 'store_001',
        productId: 'prod_999',
        sellingPrice: 80.0,
      );

      expect(storeProductId, 'sp_888-uuid-string');
    });

    test('API error throws ApiException', () async {
      final mockClient = MockClient((request) async {
        return http.Response('Server Error', 500);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      expect(
        () => repo.createProduct(name: 'Error Name', brand: 'Error Brand'),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.serverError)),
      );
    });

    test('uploadProductImage constructs multipart and parses response', () async {
      final tempDir = Directory.systemTemp.createTempSync();
      final tempFile = File('${tempDir.path}/test.jpg')..writeAsBytesSync([1, 2, 3]);

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_999/images/upload');
        expect(request.headers['content-type'], contains('multipart/form-data'));
        expect(request.body, contains('image_type'));
        expect(request.body, contains('source_type'));
        expect(request.body, contains('MERCHANT'));

        final payload = {
          'id': 'img_777-uuid-string',
          'product_id': 'prod_999',
          'storage_key': 'key_123',
          'image_type': 'MERCHANT',
          'source_type': 'MERCHANT',
          'original_filename': 'test.jpg',
          'mime_type': 'image/jpeg',
          'width': 640,
          'height': 480,
          'file_size_bytes': 3,
          'is_primary': true,
          'is_verified': true,
          'created_at': '2026-08-13T10:00:00Z'
        };
        return http.Response(jsonEncode(payload), 201);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final res = await repo.uploadProductImage(
        productId: 'prod_999',
        imagePath: tempFile.path,
        imageType: 'MERCHANT',
        sourceType: 'MERCHANT',
      );

      expect(res['id'], 'img_777-uuid-string');
      expect(res['storage_key'], 'key_123');
    });

    test('uploadProductImage failure throws ApiException', () async {
      final tempDir = Directory.systemTemp.createTempSync();
      final tempFile = File('${tempDir.path}/test.jpg')..writeAsBytesSync([1, 2, 3]);

      final mockClient = MockClient((request) async {
        return http.Response('Upload Failed', 400);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      expect(
        () => repo.uploadProductImage(
          productId: 'prod_999',
          imagePath: tempFile.path,
          imageType: 'MERCHANT',
          sourceType: 'MERCHANT',
        ),
        throwsA(isA<ApiException>().having((e) => e.type, 'type', ApiExceptionType.badRequest)),
      );
    });

    test('getProduct returns product json map', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123');
        expect(request.method, 'GET');
        return http.Response(jsonEncode({'id': 'prod_123', 'name': 'Milk'}), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final res = await repo.getProduct('prod_123');
      expect(res['id'], 'prod_123');
      expect(res['name'], 'Milk');
    });

    test('updateProduct executes PATCH request', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123');
        expect(request.method, 'PATCH');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['name'], 'New Milk');
        return http.Response('', 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      await repo.updateProduct('prod_123', {'name': 'New Milk'});
    });

    test('getProductImages returns images list', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123/images');
        expect(request.method, 'GET');
        return http.Response(jsonEncode([
          {'id': 'img_1', 'is_primary': true},
          {'id': 'img_2', 'is_primary': false}
        ]), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final res = await repo.getProductImages('prod_123');
      expect(res.length, 2);
      expect(res.first['id'], 'img_1');
    });

    test('deleteProductImage executes DELETE request', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123/images/img_1');
        expect(request.method, 'DELETE');
        return http.Response('', 204);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      await repo.deleteProductImage('prod_123', 'img_1');
    });

    test('setPrimaryImage executes PATCH request for primary endpoint', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123/images/img_1/primary');
        expect(request.method, 'PATCH');
        return http.Response('', 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      await repo.setPrimaryImage('prod_123', 'img_1');
    });

    test('getProductCompleteness parses response and metrics correctly', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/products/prod_123/completeness');
        expect(request.method, 'GET');
        return http.Response(jsonEncode({
          'product_id': 'prod_123',
          'completeness_score': 85,
          'is_complete': false,
          'has_name': true,
          'has_brand': true,
          'has_category': true,
          'has_identifiers': true,
          'has_images': true,
          'has_primary_image': false,
          'has_unit_info': true,
          'missing_fields': ['primary_image']
        }), 200);
      });

      final repo = ApiProductRepository(ApiClient(client: mockClient));
      final res = await repo.getProductCompleteness('prod_123');
      expect(res.productId, 'prod_123');
      expect(res.completenessScore, 85);
      expect(res.isComplete, false);
      expect(res.missingFields, ['primary_image']);
    });
  });
}
