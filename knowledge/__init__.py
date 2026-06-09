#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古AI知识模块
"""
from .db_manager import NovelReferenceDB
from .reference_prompt import ReferencePromptGenerator

__all__ = ['NovelReferenceDB', 'ReferencePromptGenerator']
