int getWordCount(String? text) {
  if (text == null || text.isEmpty) return 0;
  return text.split(RegExp(r'\s+')).where((word) => word.isNotEmpty).length;
}
