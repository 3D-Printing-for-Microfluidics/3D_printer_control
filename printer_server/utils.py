# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
from flask import flash


def flash_errors(form, category='warning'):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash('{0} - {1}'.format(getattr(form, field).label.text, error), category)


def calcPageNum(currentPage, totalPage):
    """Default the max page shown being 9.
    
    :param currentPage: current page number
    :param totalPage: total page number
    :returns: the page number to show in pagination
    """
    if currentPage <= 7:
        startPage, endPage = 1, totalPage
    elif currentPage - 3 < 1:
        startPage, endPage = 1, 7
    elif currentPage + 3 > totalPage:
        startPage, endPage = totalPage - 6, totalPage
    else:
        startPage, endPage = currentPage - 3, currentPage + 3

    return startPage, endPage