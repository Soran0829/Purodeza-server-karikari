class LocationRecord {
  final String deviceId;
  final double latitude;
  final double longitude;
  final int? timestamp;
  final int receivedAt;
  final double? accuracyM;
  final bool fixValid;
  final String dataSource;

  LocationRecord({
    required this.deviceId,
    required this.latitude,
    required this.longitude,
    this.timestamp,
    required this.receivedAt,
    this.accuracyM,
    required this.fixValid,
    required this.dataSource,
  });

  factory LocationRecord.fromJson(Map<String, dynamic> json) {
    return LocationRecord(
      deviceId: json['device_id'] as String,
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      timestamp: json['timestamp'] as int?,
      receivedAt: json['received_at'] as int,
      accuracyM: json['accuracy_m'] == null
          ? null
          : (json['accuracy_m'] as num).toDouble(),
      fixValid: json['fix_valid'] as bool,
      dataSource: json['data_source'] as String,
    );
  }

  bool get isSimulated => dataSource == 'simulated';

  String get sourceLabel => switch (dataSource) {
        'simulated' => 'SIMULATED',
        'gps' => 'GPS',
        _ => dataSource.toUpperCase(),
      };
}
