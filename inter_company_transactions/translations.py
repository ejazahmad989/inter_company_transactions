# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

def get_doctype_translations():
    """Get translations for doctypes"""
    try:
        translations = {
            "Inter Company Workflow": {
                "en": "Inter Company Workflow",
                "es": "Flujo de Trabajo Entre Empresas",
                "fr": "Flux de Travail Inter-Entreprises"
            },
            "Workflow Approval Request": {
                "en": "Workflow Approval Request",
                "es": "Solicitud de Aprobación de Flujo",
                "fr": "Demande d'Approbation de Flux"
            },
            "Enhanced Theme Manager": {
                "en": "Enhanced Theme Manager",
                "es": "Gestor de Temas Mejorado",
                "fr": "Gestionnaire de Thèmes Amélioré"
            },
            "Backdate Permission": {
                "en": "Backdate Permission",
                "es": "Permiso de Fecha Anterior",
                "fr": "Permission de Date Antérieure"
            }
        }
        
        return translations
        
    except Exception as e:
        frappe.log_error(f"Error getting translations: {str(e)}", "Translation Error")
        return {}