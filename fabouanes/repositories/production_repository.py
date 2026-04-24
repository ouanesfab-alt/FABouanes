from __future__ import annotations

from fabouanes.core.db_access import query_db
from fabouanes.core.helpers import load_saved_recipes


def list_production_page_context():
    batches = query_db(
        '''
        SELECT pb.*, fp.name AS finished_name,
               COALESCE((
                   SELECT STRING_AGG(r.name || ' ' || CAST(pbi.quantity AS TEXT) || ' ' || r.unit, ' + ' ORDER BY pbi.id)
                   FROM production_batch_items pbi
                   LEFT JOIN raw_materials r ON r.id = pbi.raw_material_id
                   WHERE pbi.batch_id = pb.id
               ), '') AS recipe_text
        FROM production_batches pb
        JOIN finished_products fp ON fp.id = pb.finished_product_id
        ORDER BY pb.id DESC
        '''
    )
    return {
        'productions': batches,
        'raw_materials': query_db('SELECT * FROM raw_materials ORDER BY name'),
        'products': query_db('SELECT * FROM finished_products ORDER BY name'),
    }


def production_form_context():
    raw_materials = query_db('SELECT * FROM raw_materials ORDER BY name')
    return {
        'raw_materials': raw_materials,
        'raw_materials_json': [dict(r) for r in raw_materials],
        'products': query_db('SELECT * FROM finished_products ORDER BY name'),
        'recipes': load_saved_recipes(),
    }
