import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mimamori_app/services/location_api.dart';

Map<String, dynamic> recordJson({String deviceId = 'M5STICK-001'}) => {
      'id': 1,
      'device_id': deviceId,
      'latitude': 35.681236,
      'longitude': 139.767125,
      'timestamp': null,
      'received_at': 1730000001234,
      'accuracy_m': null,
      'fix_valid': true,
      'data_source': 'simulated',
    };

void main() {
  test('latest decodes a record and sends the API key', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode(recordJson()),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = LocationApi(
      client: client,
      baseUrl: 'http://test.local:8000',
      apiKey: 'app-key',
    );

    final record = await api.latest('M5STICK-001');

    expect(record, isNotNull);
    expect(record!.deviceId, 'M5STICK-001');
    expect(record.fixValid, isTrue);
    expect(captured.url.path, '/api/v1/devices/M5STICK-001/latest');
    expect(captured.headers['X-API-Key'], 'app-key');
    api.close();
  });

  test('latest returns null on 404', () async {
    final api = LocationApi(client: MockClient((_) async => http.Response('', 404)));
    expect(await api.latest('NO-SUCH'), isNull);
    api.close();
  });

  test('history encodes the limit and parses the list', () async {
    late Uri captured;
    final client = MockClient((request) async {
      captured = request.url;
      return http.Response(jsonEncode([recordJson()]), 200);
    });
    final api = LocationApi(client: client, baseUrl: 'http://test.local:8000');

    final history = await api.history('M5STICK-SIM-001', limit: 20);

    expect(history, hasLength(1));
    expect(captured.path, '/api/v1/devices/M5STICK-SIM-001/history');
    expect(captured.queryParameters['limit'], '20');
    api.close();
  });

  test('device id stays a single encoded path segment', () async {
    late Uri captured;
    final client = MockClient((request) async {
      captured = request.url;
      return http.Response('', 404);
    });
    final api = LocationApi(client: client, baseUrl: 'http://test.local:8000');

    await api.latest('a/b?c');

    expect(captured.pathSegments, ['api', 'v1', 'devices', 'a/b?c', 'latest']);
    api.close();
  });

  test('keeps a base path prefix', () async {
    late Uri captured;
    final client = MockClient((request) async {
      captured = request.url;
      return http.Response('', 404);
    });
    final api = LocationApi(client: client, baseUrl: 'http://test.local/prefix/');

    await api.latest('D1');

    expect(captured.path, '/prefix/api/v1/devices/D1/latest');
    api.close();
  });

  test('throws on a server error', () async {
    final api = LocationApi(client: MockClient((_) async => http.Response('boom', 500)));
    await expectLater(api.latest('D1'), throwsA(isA<Exception>()));
    api.close();
  });

  test('times out instead of hanging forever', () async {
    final client = MockClient((_) => Completer<http.Response>().future);
    final api = LocationApi(
      client: client,
      timeout: const Duration(milliseconds: 20),
    );

    await expectLater(api.latest('D1'), throwsA(isA<TimeoutException>()));
    api.close();
  });
}
