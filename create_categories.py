# create_categories.py

from app import app, db, Categoria
from sqlalchemy.exc import IntegrityError

# Aseguramos el contexto de la aplicación
with app.app_context():
    print("Iniciando script para gestionar categorías...")

    # Lista de categorías que queremos asegurar que existan
    categorias_a_crear = ['Sin TACC', 'Vegano', 'Lácteos', 'Orgánico', 'Cereales', 'Aceites', 'Gluten Free', 'Natural']

    for cat_nombre in categorias_a_crear:
        # Intenta encontrar la categoría por su nombre (ignorando mayúsculas/minúsculas para evitar duplicados lógicos)
        # Aunque tu modelo Categoria.nombre es unique y exacto, esta es una buena práctica
        existing_cat = Categoria.query.filter(db.func.lower(Categoria.nombre) == db.func.lower(cat_nombre)).first()

        if existing_cat is None:
            # Si no existe, créala
            print(f"  - Creando categoría: '{cat_nombre}'")
            new_cat = Categoria(nombre=cat_nombre)
            db.session.add(new_cat)
        else:
            print(f"  - La categoría '{cat_nombre}' ya existe. (ID: {existing_cat.id})")

    try:
        db.session.commit() # Intenta guardar los cambios
        print("\nOperación de adición/verificación de categorías completada.")
    except IntegrityError:
        db.session.rollback() # Si hubo un error (ej. una race condition), deshaz los cambios
        print("\nError al guardar categorías (posible duplicado inesperado). Revirtiendo cambios.")

    # --- Listar TODAS las categorías actuales en la base de datos ---
    print("\n--- Categorías actuales en la base de datos ---")
    all_categories = Categoria.query.order_by(Categoria.nombre).all()
    if all_categories:
        for cat in all_categories:
            print(f"ID: {cat.id}, Nombre: {cat.nombre}")
    else:
        print("¡ATENCIÓN: No hay categorías en la base de datos después de la ejecución!")

    print("\nScript de categorías finalizado.")
