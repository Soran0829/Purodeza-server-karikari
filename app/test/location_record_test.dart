import 'package:flutter_test/flutter_test.dart';
import 'package:mimamori_app/models/location_record.dart';

void main() {
  test('parses a complete record', () {
    final record = LocationRecord.fromJson({
      'id': 1,
      'device_id': 'M5STICK-001',
      'latitude': 35.681236,
      'longitude': 139.767125,
      'timestamp': 1730000000000,
      'received_at': 1730000001234,
      'accuracy_m': 12.5,
      'fix_valid': true,
      'data_source': 'gps',
    });

    expect(record.deviceId, 'M5STICK-001');
    expect(record.latitude, 35.681236);
    expect(record.longitude, 139.767125);
    expect(record.timestamp, 1730000000000);
    expect(record.receivedAt, 1730000001234);
    expect(record.accuracyM, 12.5);
    expect(record.fixValid, isTrue);
    expect(record.sourceLabel, 'GPS');
  });

  test('keeps unknown accuracy and timestamp as null', () {
    final record = LocationRecord.fromJson({
      'device_id': 'M5STICK-001',
      'latitude': 35.0,
      'longitude': 139.0,
      'timestamp': null,
      'received_at': 1730000001234,
      'accuracy_m': null,
      'fix_valid': false,
      'data_source': 'simulated',
    });

    expect(record.timestamp, isNull);
    expect(record.accuracyM, isNull);
    expect(record.fixValid, isFalse);
    expect(record.isSimulated, isTrue);
    expect(record.sourceLabel, 'SIMULATED');
  });

  test('accepts integer coordinates', () {
    final record = LocationRecord.fromJson({
      'device_id': 'M5STICK-001',
      'latitude': 35,
      'longitude': 139,
      'received_at': 1,
      'fix_valid': true,
      'data_source': 'gps',
    });

    expect(record.latitude, 35.0);
    expect(record.longitude, 139.0);
  });

  test('shows the raw label for a future data source', () {
    final record = LocationRecord.fromJson({
      'device_id': 'M5STICK-001',
      'latitude': 35.0,
      'longitude': 139.0,
      'received_at': 1,
      'fix_valid': true,
      'data_source': 'wifi',
    });

    expect(record.isSimulated, isFalse);
    expect(record.sourceLabel, 'WIFI');
  });
}
