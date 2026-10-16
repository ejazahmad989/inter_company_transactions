import frappe


def get_doctype_translations():
    """Get translations for doctypes"""
    try:
        translations = {
            "Intercompany Transaction Link": {
                "en": "Intercompany Transaction Link",
                "es": "Enlace de Transacción Entre Empresas",
                "fr": "Lien de Transaction Inter-Entreprises"
            },
            "Inter Company Settings": {
                "en": "Inter Company Settings",
                "es": "Configuración Entre Empresas",
                "fr": "Paramètres Inter-Entreprises"
            },
            "Inter Company Document Reference": {
                "en": "Inter Company Document Reference",
                "es": "Referencia de Documento Entre Empresas",
                "fr": "Référence de Document Inter-Entreprises"
            },
            "Inter Company Netting Cycle": {
                "en": "Inter Company Netting Cycle",
                "es": "Ciclo de Compensación Entre Empresas",
                "fr": "Cycle de Compensation Inter-Entreprises"
            },
            "Transfer Pricing Policy": {
                "en": "Transfer Pricing Policy",
                "es": "Política de Precios de Transferencia",
                "fr": "Politique de Prix de Transfert"
            },
            "Inter Company Elimination Run": {
                "en": "Inter Company Elimination Run",
                "es": "Ejecución de Eliminación Entre Empresas",
                "fr": "Exécution d'Élimination Inter-Entreprises"
            },
            "Inter Company Dispute": {
                "en": "Inter Company Dispute",
                "es": "Disputa Entre Empresas",
                "fr": "Litige Inter-Entreprises"
            }
        }
        return translations
    except Exception as e:
        frappe.log_error(f"Error getting translations: {e!s}", "Translation Error")
        return {}
