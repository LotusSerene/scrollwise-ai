# chapter_generator_loop.py
import json
import os
from typing import Dict, Any, Tuple, List
from context_manager import ContextManager
from chapter_generator import ChapterGenerator
import logging
import tempfile

class ChapterGeneratorLoop:

    def __init__(self, api_key: str, generation_model: str, check_model: str):
        self.api_key = api_key
        self.generation_model = generation_model
        self.check_model = check_model
        self.logger = logging.getLogger(__name__)

    def generate_chapter(self, chapter_number: int, plot: str, writing_style: str, instructions: Dict[str, Any], characters: Dict[str, Any], previous_chapters: List[Dict[str, Any]]) -> Tuple[str, str, Dict[str, Any]]:
        chapter_generator = ChapterGenerator(self.api_key, self.generation_model, self.check_model)
        context_manager = ContextManager()
        self.add_context(context_manager, plot, writing_style, instructions, characters)
        context = context_manager.get_context()
        chapter, chapter_title, validity = chapter_generator.generate_chapter(chapter_number, plot, writing_style, instructions, characters, previous_chapters)
        return chapter, chapter_title, validity

    def add_context(self, context_manager: ContextManager, plot: str, writing_style: str, instructions: Dict[str, Any], characters: Dict[str, Any]):
        context_manager.add_plot_point(plot)
        context_manager.add_other_element(f"Writing style: {writing_style}")
        context_manager.add_other_element(f"Additional instructions: {instructions}")
        for name, description in characters.items():
            context_manager.add_character(name, description)
