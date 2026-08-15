import 'package:flutter_test/flutter_test.dart';
import 'package:packready/main.dart';

void main() {
  testWidgets('PackReady smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const PackReadyApp());
    // Basic smoke test — just ensure the app mounts
    expect(find.byType(PackReadyApp), findsOneWidget);
    
    // Let the splash screen timer complete to avoid pending timer assertion
    await tester.pump(const Duration(seconds: 2));
  });
}
