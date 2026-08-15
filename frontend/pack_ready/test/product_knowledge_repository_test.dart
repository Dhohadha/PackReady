import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:packready/core/network/api_client.dart';
import 'package:packready/core/network/api_config.dart';
import 'package:packready/shared/models/product_knowledge_result.dart';
import 'package:packready/shared/services/api_product_knowledge_repository.dart';

void main() {
  setUp(() {
    ApiConfig.baseUrl = 'http://testapi.local';
  });

  group('ProductKnowledgeResult Model Tests', () {
    test('parses successful lookup response with full candidate info', () {
      final json = {
        'found': true,
        'match': {
          'name': 'Milkybar Create',
          'brand': 'Nestle',
          'description': 'White Chocolate',
          'unit_value': 42.0,
          'unit_type': 'g',
        },
        'identifiers': [
          {'type': 'EAN', 'value': '8901058861921'}
        ],
        'images': [
          {
            'url': 'https://images.openfoodfacts.org/1.jpg',
            'provider': 'Open Food Facts',
            'image_role': 'REFERENCE'
          }
        ],
        'sources': [
          {
            'provider_name': 'Open Food Facts',
            'source_type': 'EXTERNAL_DATABASE',
            'external_id': '8901058861921',
            'source_url': 'https://world.openfoodfacts.org/product/8901058861921',
            'retrieved_at': '2026-08-13T16:32:03Z'
          }
        ],
        'confidence': 'MEDIUM',
        'provider_status': {
          'PackReady Local DB': 'NOT_FOUND',
          'Open Food Facts': 'FOUND',
          'UPCitemdb': 'NOT_FOUND'
        }
      };

      final result = ProductKnowledgeResult.fromJson(json);

      expect(result.found, isTrue);
      expect(result.match, isNotNull);
      expect(result.match!.name, equals('Milkybar Create'));
      expect(result.match!.brand, equals('Nestle'));
      expect(result.match!.unitValue, equals(42.0));
      expect(result.match!.unitType, equals('g'));
      expect(result.images.length, equals(1));
      expect(result.images.first.url, equals('https://images.openfoodfacts.org/1.jpg'));
      expect(result.sources.length, equals(1));
      expect(result.sources.first.providerName, equals('Open Food Facts'));
      expect(result.confidence, equals('MEDIUM'));
    });

    test('handles missing optional fields safely without throwing', () {
      final json = {
        'found': true,
        'match': {
          'name': 'Generic Product',
          'brand': null,
          'description': null,
          'unit_value': null,
          'unit_type': null,
        },
        'identifiers': [],
        'images': [],
        'sources': [],
        'confidence': 'LOW',
        'provider_status': {}
      };

      final result = ProductKnowledgeResult.fromJson(json);

      expect(result.found, isTrue);
      expect(result.match!.name, equals('Generic Product'));
      expect(result.match!.brand, isNull);
      expect(result.match!.unitValue, isNull);
      expect(result.images, isEmpty);
      expect(result.sources, isEmpty);
      expect(result.confidence, equals('LOW'));
    });

    test('parses not found response correctly', () {
      final json = {
        'found': false,
        'match': null,
        'identifiers': [
          {'type': 'EAN', 'value': '0000000000000'}
        ],
        'images': [],
        'sources': [],
        'confidence': 'UNKNOWN',
        'provider_status': {'PackReady Local DB': 'NOT_FOUND'}
      };

      final result = ProductKnowledgeResult.fromJson(json);

      expect(result.found, isFalse);
      expect(result.match, isNull);
      expect(result.confidence, equals('UNKNOWN'));
    });
  });

  group('ApiProductKnowledgeRepository Tests', () {
    test('lookupProduct calls correct endpoint with parameters', () async {
      final mockResponse = {
        'found': true,
        'match': {
          'name': 'Milkybar',
          'brand': 'Nestle',
          'unit_value': 42.0,
          'unit_type': 'g'
        },
        'identifiers': [],
        'images': [],
        'sources': [],
        'confidence': 'HIGH',
        'provider_status': {'PackReady Local DB': 'FOUND'}
      };

      final mockClient = MockClient((request) async {
        expect(request.url.path, '/product-knowledge/lookup');
        expect(request.url.queryParameters['identifier_type'], 'EAN');
        expect(request.url.queryParameters['value'], '8901058861921');
        return http.Response(jsonEncode(mockResponse), 200);
      });

      final apiClient = ApiClient(client: mockClient);
      final repository = ApiProductKnowledgeRepository(apiClient);

      final result = await repository.lookupProduct(
        identifierType: 'EAN',
        value: '8901058861921',
      );

      expect(result.found, isTrue);
      expect(result.match!.name, equals('Milkybar'));
      expect(result.confidence, equals('HIGH'));
    });
  });
}
