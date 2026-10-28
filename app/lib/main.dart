import 'dart:async';

import 'package:flutter/material.dart';

import 'models/location_record.dart';
import 'services/location_api.dart';

/// Keep in sync with the server's STALE_THRESHOLD_MS.
const int _staleThresholdMs = int.fromEnvironment(
  'STALE_THRESHOLD_MS',
  defaultValue: 30000,
);

void main() {
  runApp(const MimamoriApp());
}

class MimamoriApp extends StatelessWidget {
  const MimamoriApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mimamori Test',
      theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _api = LocationApi();
  final _deviceIdController = TextEditingController(text: 'M5STICK-SIM-001');
  String get _deviceId => _deviceIdController.text.trim();

  LocationRecord? _current;
  List<LocationRecord> _history = [];
  String? _error;
  bool _loading = false;
  bool _inFlight = false;
  DateTime? _lastSuccessAt;

  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _deviceIdController.dispose();
    _api.close();
    super.dispose();
  }

  Future<void> _refresh() async {
    // The 5s timer can fire before a slow previous poll finishes; skip
    // overlapping calls so an old response cannot overwrite newer state.
    if (_inFlight) return;
    final deviceId = _deviceId;
    if (deviceId.isEmpty) return;

    _inFlight = true;
    setState(() => _loading = true);
    try {
      final current = await _api.latest(deviceId);
      final history = await _api.history(deviceId, limit: 20);
      if (!mounted) return;
      setState(() {
        _current = current;
        _history = history;
        _error = null;
        _lastSuccessAt = DateTime.now();
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    } finally {
      _inFlight = false;
      if (mounted) setState(() => _loading = false);
    }
  }

  bool get _stale {
    final c = _current;
    if (c == null) return false;
    final ageMs = DateTime.now().millisecondsSinceEpoch - c.receivedAt;
    return ageMs > _staleThresholdMs;
  }

  String _formatTime(int ms) {
    final dt = DateTime.fromMillisecondsSinceEpoch(ms).toLocal();
    String two(int v) => v.toString().padLeft(2, '0');
    return '${dt.year}-${two(dt.month)}-${two(dt.day)} '
        '${two(dt.hour)}:${two(dt.minute)}:${two(dt.second)}';
  }

  @override
  Widget build(BuildContext context) {
    final c = _current;
    return Scaffold(
      appBar: AppBar(title: const Text('Mimamori Test')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              controller: _deviceIdController,
              decoration: const InputDecoration(labelText: 'Device ID'),
              onSubmitted: (_) => _refresh(),
            ),
            const SizedBox(height: 12),
            if (_loading) const LinearProgressIndicator(),
            if (_error != null)
              Card(
                color: Colors.red.shade50,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text('Communication error: $_error'),
                ),
              ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Current position', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    if (c == null)
                      const Text('No data')
                    else ...[
                      Text('Lat: ${c.latitude.toStringAsFixed(6)}'),
                      Text('Lon: ${c.longitude.toStringAsFixed(6)}'),
                      Text('Source: ${c.sourceLabel}'),
                      Text('Fix: ${c.fixValid ? "VALID" : "INVALID"}'),
                      Text('Accuracy: ${c.accuracyM == null ? "N/A" : "${c.accuracyM} m"}'),
                      Text('Device timestamp: ${c.timestamp == null ? "N/A" : _formatTime(c.timestamp!)}'),
                      Text('Received at: ${_formatTime(c.receivedAt)}'),
                      if (_stale)
                        Text(
                          'STALE (last update ${DateTime.now().millisecondsSinceEpoch - c.receivedAt} ms ago)',
                          style: const TextStyle(color: Colors.orange, fontWeight: FontWeight.bold),
                        ),
                    ],
                    const SizedBox(height: 8),
                    Text('Last successful poll: ${_lastSuccessAt?.toLocal() ?? "-"}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Text('History', style: Theme.of(context).textTheme.titleMedium),
            if (_history.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text('No history'),
              ),
            ..._history.map(
              (h) => ListTile(
                title: Text('${h.latitude.toStringAsFixed(5)}, ${h.longitude.toStringAsFixed(5)}'),
                subtitle: Text('${h.sourceLabel}  received ${_formatTime(h.receivedAt)}'),
                trailing: Text(h.fixValid ? 'FIX' : 'NOFIX'),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _refresh,
        child: const Icon(Icons.refresh),
      ),
    );
  }
}
