import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/location_record.dart';

class LocationApi {
  LocationApi({
    http.Client? client,
    this.baseUrl = const String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8000',
    ),
    this.apiKey = const String.fromEnvironment(
      'APP_API_KEY',
      defaultValue: 'dev-app-key-change-me',
    ),
    this.timeout = const Duration(seconds: 10),
  }) : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;
  final String apiKey;

  /// Without an explicit timeout a stalled connection leaves the request
  /// pending forever, and the polling loop never runs again.
  final Duration timeout;

  void close() => _client.close();

  Map<String, String> get _headers => {'X-API-Key': apiKey};

  /// Builds the URL with proper path/query encoding so a device id that
  /// contains '/', '?' or spaces cannot escape the intended endpoint.
  Uri _uri(String deviceId, String suffix, [Map<String, String>? query]) {
    final base = Uri.parse(baseUrl);
    return base.replace(
      pathSegments: [
        ...base.pathSegments.where((segment) => segment.isNotEmpty),
        'api',
        'v1',
        'devices',
        deviceId,
        suffix,
      ],
      queryParameters: query,
    );
  }

  Future<http.Response> _get(Uri uri) =>
      _client.get(uri, headers: _headers).timeout(timeout);

  Future<LocationRecord?> latest(String deviceId) async {
    final resp = await _get(_uri(deviceId, 'latest'));
    if (resp.statusCode == 404) return null;
    if (resp.statusCode != 200) {
      throw Exception('latest failed: ${resp.statusCode} ${resp.body}');
    }
    return LocationRecord.fromJson(jsonDecode(resp.body) as Map<String, dynamic>);
  }

  Future<List<LocationRecord>> history(String deviceId, {int limit = 50}) async {
    final resp = await _get(_uri(deviceId, 'history', {'limit': '$limit'}));
    if (resp.statusCode != 200) {
      throw Exception('history failed: ${resp.statusCode} ${resp.body}');
    }
    final list = jsonDecode(resp.body) as List<dynamic>;
    return list
        .map((e) => LocationRecord.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}
