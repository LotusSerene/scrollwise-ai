import 'package:flutter/material.dart';
import 'dart:io';
import 'package:fluttertoast/fluttertoast.dart';

class AppNotification {
  static void show(BuildContext context, String message,
      {bool isError = false}) {
    if (Platform.isWindows) {
      // Show SnackBar for Windows
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(message),
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.all(8),
          backgroundColor: isError
              ? Theme.of(context).colorScheme.error
              : Theme.of(context).colorScheme.primaryContainer,
          duration: const Duration(seconds: 4),
          action: SnackBarAction(
            label: 'Dismiss',
            textColor: isError
                ? Theme.of(context).colorScheme.onError
                : Theme.of(context).colorScheme.onPrimaryContainer,
            onPressed: () {
              ScaffoldMessenger.of(context).hideCurrentSnackBar();
            },
          ),
        ),
      );
    } else {
      // Use Fluttertoast for other platforms
      Fluttertoast.showToast(msg: message);
    }
  }
}
