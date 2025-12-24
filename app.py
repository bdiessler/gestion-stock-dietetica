#Importo funciones utiles
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy                                                 #DB
from flask_migrate import Migrate
from datetime import datetime, timezone
# from slqalchemy import or_
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Boolean, Table, ForeignKey
from flask_wtf import FlaskForm                                                         #Form
from wtforms import StringField, FloatField, IntegerField, SubmitField, TextAreaField, SelectField, SelectMultipleField   #Form
from wtforms.validators import DataRequired, Length, NumberRange, Optional              #Form
from wtforms.widgets import ListWidget, CheckboxInput
from flask_wtf.file import FileField, FileAllowed, FileRequired                         #Form
from werkzeug.utils import secure_filename                                              #Img
import uuid                                                                             #Img

import unicodedata                                                                      #Busqueda sin tildes
import re                                                                               #Busqueda sin tildes
import os


# --- Configuracion de la app web --- #
app = Flask(__name__)
#Cambiar en produccion
app.config['SECRET_KEY']= 'clave_secreta'

# --- Configuracion DB SQLAlchemy, usamos SQLite --- #
basedir= os.path.abspath(os.path.dirname(__file__)) #Obtengo el path de este archivo
app.config['SQLALCHEMY_DATABASE_URI']= 'sqlite:///' + os.path.join(basedir, 'inventario.db') #Donde guardamos la db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']= False #Desactiva seguimiento de modificaciones para ahorrar memoria

# --- Configuracion para la subida de imagenes --- #
app.config['UPLOAD_FOLDER']= os.path.join(basedir, 'static/uploads/productos')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) #Crea la carpeta si no existe, si existe no hace nada
app.config['MAX_CONTENT_LENGTH']= 16 * 1024 * 1024 # 16MB para archivos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # Extensiones para las imágenes



# --- Funciones Auxiliares --- #

#rsplit divide el archivo buscando el primer parametro desde la derecha, la cantidad de veces que tenga en el segundo parametro
#despues del rsplit [1] es la cola y [0] la head, .lower convierte a minusculas
#Chequeamos que tenga una extension valida y no tenga el nombre vacio
def allowed_file(filename):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#Generamos un nombre unico para que no haya problemas de repeticion
def generate_unique_filename(filename):
    ext= filename.rsplit('.',1)[1].lower()
    unique_name= str(uuid.uuid4())
    return f'{unique_name}.{ext}'

#Normalizamos texto para una busqueda que no tenga en cuenta la diferencia entre caracteres acentuados y no acentuados
def normalize_text(text):
    #Si es vacio no hacemos nada
    if text is None:
        return None
    
    #Convertimos a minuscula
    text = text.lower()

    # Eliminar acentos y diacríticos
    #El ".normalize" separa por ejemplo "é" en "e" y "´"
    #".category() = 'Mn'" representa a los caracteres "Mark, Nonspacing" (tildes, elevaciones, etc)
    #".join" reconstruye el string sin estos caracteres
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    

    #Remover caracteres que no sean letras, números o espacios
    #"[]" conjunto de caracteres, "[^...]" negacion, "a-z0-9\s" letras, numeros y espacios 
    #Todo esto quiere decir que cualquier caracter que no sea una letra, un numero o un espacio se va a borrar
    text = re.sub(r'[^a-z0-9\s]', '', text) 
    
    #Elimino espacios del principio o final del string
    text = text.strip()

    #Cualquier multiple espacio es reemplazado por un espacio solo
    text = re.sub(r'\s+', ' ', text)

    # Si despues de normalizar queda vacio retornamos None
    if text:
        return text
    else:
        return None





db= SQLAlchemy(app)
migrate= Migrate(app, db)



# --- Modelado de la DB --- #

#Tabla de asociacion muchos a muchos entre Producto y Categoria
#ForeignKey. producto_id debe existir en la tabla de productos
producto_categoria= db.Table('producto_categoria',
    db.Column('producto_id', db.Integer, db.ForeignKey('producto.id'), primary_key=True),                       
    db.Column('categoria_id', db.Integer, db.ForeignKey('categoria.id'), primary_key=True)                       
)



class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False) # Nombre del producto (ej. "Harina de Almendras")
    nombre_normalizado= db.Column(db.String(150), nullable= False, default='')
    marca = db.Column(db.String(100), nullable=False) # Marca del producto (ej. "Natura", "Arcor")
    marca_normalizada= db.Column(db.String(150), nullable= False, default='')
    descripcion = db.Column(db.Text, nullable=True) # Descripción detallada del producto
    precio = db.Column(db.Float, nullable=False) # Precio de venta
    stock = db.Column(db.Integer, nullable=False, default=0) # Cantidad disponible en inventario
    imagen_url = db.Column(db.String(255), nullable=True) # Ruta relativa a la imagen del producto
    #Agrego fechas de creacion y actualizacion para mayor informacion futura
    fecha_creacion= db.Column(db.DateTime, default=datetime.now(timezone.utc))
    fecha_actualizacion= db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate= datetime.now(timezone.utc))

    #Relacion muchos a muchos con Categoria
    #bkacref='productos' accede a los productos de una categoria (categoria.productos)
    #Basicamente permite que accedamos a todos los productos de una categoria
    categorias= db.relationship('Categoria', secondary= producto_categoria, backref=db.backref('productos', lazy='dynamic'))


    #definimos que un producto es unico en base al conjunto de su nombre y marca
    __table_args__ = (db.UniqueConstraint('nombre', 'marca', name='_nombre_marca_uc'),)


    #funcion de return
    def __repr__(self):
        return f'<Producto {self.nombre} - {self.marca}'
    
# --- Categorias --- #
class Categoria(db.Model):
    id= db.Column(db.Integer, primary_key=True)
    nombre= db.Column(db.String(100), nullable= False, unique= True)


    def __repr__(self):
        return f'<Categoria {self.nombre}>'
    
# --- Formulario de Categorias--- #
#Este form es para crear nuevas categorias
class CategoriaForm(FlaskForm):
    nombre= StringField('Nombre de la Categoria', validators=[DataRequired(), Length(min= 1, max= 100)])
    submit= SubmitField('Guardar Categoria')

# --- Formulario del Producto--- #
class ProductoForm(FlaskForm):
    nombre= StringField('Nombre del Producto', validators=[DataRequired(), Length(min=1, max=150)])
    marca= StringField('Marca del Producto', validators=[DataRequired(), Length(min=1, max=150)])
    descripcion= TextAreaField('Descripcion (opcional)', validators=[Optional(), Length(max=500)])
    precio= FloatField('Precio (ej. 123.45)', validators=[DataRequired(), NumberRange(min=0.01, message='El precio debe ser mayor a 0.')])
    stock= IntegerField('Stock Disponible', validators=[DataRequired(), NumberRange(min=0, message='El stock no puede ser negativo.')])
    #Nuevas categorias
    categorias= SelectMultipleField('Categorias',
                                    validators= [Optional()], #No es obligatorio tener categoria
                                    coerce= int,    #Convierte el valor seleccionado a entero (ID de categoria)
                                    widget= ListWidget(prefix_label=False),
                                    option_widget= CheckboxInput())    
    
    #Campo de la imagen, mensaje del form, tiene que ser una de las extensiones permitidas
    imagen= FileField('Imagen del Producto (opcional)', validators=[FileAllowed(ALLOWED_EXTENSIONS, 'El formato de la imagen debe ser .png, .jpg, .jpeg o .gif')])
    submit= SubmitField('Guardar Producto')


    #COmo las categorias son dinamicas hay que reinicializarla al crear una nueva instancia
    #Carga dinamicamente las opciones del campo de categorias
    def __init__(self, *args, **kwargs):
        #Llama al constructor original, esto inicializa las propiedaades basicas del formulario (las de arriba)
        super(ProductoForm, self).__init__(*args, **kwargs)
        #Carga las categorias existentes de la DB para rellenar las opciones del campo categorias
        self.categorias.choices= [(c.id, c.nombre) for c in Categoria.query.order_by('nombre').all()]
# --- --- Rutas de la app --- --- #

# /// Inicio /// #
@app.route('/')
def inicio():
    #Obtenemos el numero de la pagina actual por la URL
    page= request.args.get('page', 1, type=int)
    #Cuantos producto por pagina queremos
    per_page= 21

    #Obtenemos el termino de busca del URL (si existe)
    search_query= request.args.get('q')


    #Ubicamos los IDs de las categorias a filtrar
    selected_category_ids_filter= request.args.getlist('categorias_filtro', type=int)
    #Para elegir si las categorias son or o and
    logic_type_filter= request.args.get('logic_type', 'and') #Defaut= 'and'


    #Parametros de orden
    #Categoria de orden (nombre, marca, precio, stock, etc)
    sort_by= request.args.get('sort_by', 'id') #Por defecto ID
    #Ascendente o descendente
    order= request.args.get('order', 'asc')    #Por defecto ascendente


    #Creamos una query inicial, por si no se aplican filtro hacemos la paginacion en base a esta query
    query= Producto.query



    #En caso de que haya busqueda:
    if search_query:
        #Normalizamos la busqueda
        normalized_search_query= normalize_text(search_query)

        #Verificamos que despues de normalizar no quede vacio
        if normalized_search_query:
            #Buscamos por nombre o marca (normalizado)
            #".ilike" es case-insensitive
            #"%" Puede haber cualquier cosa antes o despues del searchquery
            query= query.filter(
                (Producto.nombre_normalizado.ilike(f'%{normalized_search_query}%')) |
                (Producto.marca_normalizada.ilike(f'%{normalized_search_query}%'))
            )
            #Si no se encontraron productos para el filtro
            if not query.count():
                flash(f'No se encontraron productos para "{normalized_search_query}".', 'info')
            else:
                #Mostramos la busqueda normalizada para mostrar efectivamente los caracteres que son tenidos en cuenta a la hora de buscar
                flash(f'Mostrando los resultados para "{normalized_search_query}".', 'info')
#
        #Si despues de normalizar quedo vacia
        else:
            #Mostramos todos los productos
            todos_los_productos= Producto.query.all()
            #Avisamos que paso algo raro
            flash(f'Busqueda sin caracteres validos. Mostrando todos los productos', 'warning')

    #Filtrado por categoria
    if selected_category_ids_filter:
        #Si la logica es and
        if logic_type_filter == 'and':
            for cat_id in selected_category_ids_filter:
                query= query.filter(Producto.categorias.any(Categoria.id == cat_id))
            flash(f'Mostrando productos que contienen SIMULTANEAMENTE estas categorias: {[c.nombre for c in Categoria.query.filter(Categoria.id.in_(selected_category_ids_filter)).all()]}', 'info')
        #Si la logica es or
        else:
            query= query.filter(Producto.categorias.any(Categoria.id.in_(selected_category_ids_filter)))
            flash(f'Mostrando productos que contienen CUALQUIERA de estas categorias: {[c.nombre for c in Categoria.query.filter(Categoria.id.in_(selected_category_ids_filter)).all()]}', 'info')




    #Ordenamiento de columnas. Mapeamos en un diccionario los nombres a los atributos
    sortable_columns={
        'id': Producto.id,
        'nombre': Producto.nombre_normalizado, # Normalizado
        'marca': Producto.marca_normalizada,   # Normalizada
        'precio': Producto.precio,
        'stock': Producto.stock
    }

    #Verificamos que sea sort_by sea una de las categorias validas, si no ID
    column_to_sort= sortable_columns.get(sort_by, Producto.id)

    #Checkeamos en que orden se ordena
    if order == 'desc':
        query= query.order_by(column_to_sort.desc())
    else:
        query= query.order_by(column_to_sort.asc())

    #Hacemos la paginacion con o sin filtrado y en el orden correcto
    #error_out si esta en false NO te manda a un 404, te manda a la pagina 1
    productos_paginados= query.paginate(page=page, per_page=per_page, error_out=False)

#Esto lo hacemos para un badge del frontend
    total_productos = Producto.query.count()
    
    return render_template(
        'index.html',
        nombre_usuario= 'Admin',
        productos= productos_paginados.items,   #Items de la pagina actual
        pagination= productos_paginados,        #Objeto de paginacion completo
        search_query= search_query,             #Mantenemos el search query
        sort_by= sort_by,                       #Mantenemos categoria de orden
        order= order,                            #Mantenemos ascendente o descendente

        #Pasamos categorias para el selector de categorias
        todas_las_categorias_disponibles= [(c.id, c.nombre) for c in Categoria.query.order_by('nombre').all()],
        #Pasamos los IDs de categorias marcadas para que se mantengan
        selected_category_ids_filter= selected_category_ids_filter,
        #Pasamos la logica de filtrado para que se mantenga
        logic_type_filter= logic_type_filter,
        # Pasamos el total de productos para el badge
        total_productos=total_productos
    )


# /// Agregar Producto /// #
@app.route('/agregar_producto', methods=['GET', 'POST'])
def agregar_producto():
    #Iniciamos un form para agregar productos
    form= ProductoForm()

    #Al mandar el form
    if form.validate_on_submit():
        #Obtener las categorias seleccionadas por sus IDs
        selected_category_ids = form.categorias.data
        #Crear la lista de objetvos de la categoria
        selected_categories= Categoria.query.filter(Categoria.id.in_(selected_category_ids)).all()

        #Normalizo los nombres para que tambien verifique la unicidad
        nombre_norm= normalize_text(form.nombre.data)
        marca_norm= normalize_text(form.marca.data)  

        #Verifico unicidad con nombres normalizados
        producto_existente= Producto.query.filter_by(
            nombre_normalizado= nombre_norm,    #nombre igual al del form
            marca_normalizada= marca_norm       #marca igual a la del form
        ).first()

        #Caso donde el producto ya existe
        if producto_existente:
            #Notificamos el error
            form.nombre.errors.append('Ya existe este producto con este Nombre y Marca.')
            #Volvemos a que llene nuevamente el form
            return render_template('agregar_producto.html', form= form)
        
        #Caso donde el producto NO existe aun
        else:
        # - Subida de imagen - #
        #Por defecto no hay imagen
            imagen_filename= None
        #Si se subio un archivo con nombre 'imagen'
            if 'imagen' in request.files:
                file= request.files['imagen']
                #Verifico que el archivo sea valido
                if file.filename != '' and allowed_file(file.filename):
                    #Generamos un nombre unico (y seguro) para la imagen
                    unique_filename= generate_unique_filename(secure_filename(file.filename))
                    #Guardamos el filepath. Une el primer parametro con el segundo o tercero si hubiera
                    filepath= os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    #Guardamos el archivo en el filepath
                    file.save(filepath)
                    #Guardamos el nombre unico del archivo
                    imagen_filename= unique_filename


            #Creamos el producto con los datos del form
            nuevo_producto= Producto(
                nombre=form.nombre.data,
                marca=form.marca.data,
                descripcion=form.descripcion.data,
                precio=form.precio.data,
                stock=form.stock.data,
                imagen_url= imagen_filename,
                #Agregamos los nombres normalizados
                nombre_normalizado= nombre_norm,
                marca_normalizada= marca_norm
            )

            #Añadimos las categorias seleccionadas
            for cat in selected_categories:
                nuevo_producto.categorias.append(cat)


            #Marcamos el producto a añadir en la DB
            db.session.add(nuevo_producto)
            #Lo añadimos
            db.session.commit()
            #Avisamos que salio bien
            flash(f'Producto "{nuevo_producto.nombre} - {nuevo_producto.marca}" agregado con exito', 'success')
            #Volvemos al inicio
            return redirect(url_for('inicio'))
        
    #En caso de que la peticion sea GET, renderizamos el formulario vacio
    return render_template('agregar_producto.html', form= form)

# /// Editar Producto /// #
@app.route('/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    #Buscamos el la DB el producto a editar
    producto= Producto.query.get_or_404(id)
    #Creamos el formulario para editar
    form= ProductoForm(obj=producto)


    #Caso donde ya rellenamos la edicion
    if form.validate_on_submit():
        #Normalizamos los datos del form para verificar unicidad
        nombre_norm_form= normalize_text(form.nombre.data)
        marca_norm_form= normalize_text(form.marca.data)


        #Vemos si el producto editado ya existe (con nombres formalizados)
        producto_existente_otro= Producto.query.filter(
            Producto.nombre_normalizado == nombre_norm_form,
            Producto.marca_normalizada == marca_norm_form,
            Producto.id != producto.id #Excluimos al mismo producto, sino siempre da mal
        ).first()

        #Caso donde ya existe ese producto
        if producto_existente_otro:
            form.nombre.errors.append('Ya existe otro producto con este Nombre y Marca.')
            #Lo renderizamos nuevamente para mostrar el error
            return render_template('editar_producto.html', form=form, producto=producto)


        #Caso donde no existe ese producto
        else:
            #Guardo el filename del producto actual por si NO lo tengo que actualizar
            imagen_filename= producto.imagen_url
            #Caso de actualizacion de imagen
            if form.imagen.data and allowed_file(form.imagen.data.filename):
                file= form.imagen.data
                if file.name != '' and allowed_file(file.filename):
                    #Caso donde hay una imagen vieja
                    if producto.imagen_url:
                        #Guardamos el path de la imagen vieja
                        old_image_path= os.path.join(app.config['UPLOAD_FOLDER'], producto.imagen_url)
                        #Si existe ese path entonces lo eliminamos
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    
                    #Caso donde NO hay una imagen vieja
                    #Generamos un nombre unico (y seguro) para la imagen
                    unique_filename= generate_unique_filename(secure_filename(file.filename))
                    #Guardamos el filepath. Une el primer parametro con el segundo o tercero si hubiera
                    filepath= os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    #Guardamos el archivo en el filepath
                    file.save(filepath)
                    #Guardamos el nombre unico del archivo
                    imagen_filename= unique_filename

            #Actualizamos los datos del producto
            producto.nombre = form.nombre.data
            producto.marca = form.marca.data
            producto.descripcion = form.descripcion.data
            producto.precio = form.precio.data
            producto.stock = form.stock.data

            #Manejo de categorias
            #Limpiamos las actuales
            producto.categorias.clear()
            #Obtenemos las categorias por sus IDs
            selected_category_ids = form.categorias.data
            #Añadimos las nuevas categorias
            selected_categories= Categoria.query.filter(Categoria.id.in_(selected_category_ids)).all()
            for cat in selected_categories:
                producto.categorias.append(cat)

            #Actualizamos la imagen
            producto.imagen_url= imagen_filename

            #Actualizamos los nombres normalizados
            producto.nombre_normalizado= nombre_norm_form
            producto.marca_normalizada= marca_norm_form

            #Confirmamos los cambios en la DB
            db.session.commit()
            #Mensaje de que salio bien
            flash(f'El producto "{producto.nombre} - {producto.marca}" fue actualizado con exito.', 'success')
            #Volvemos al inicio
            return redirect(url_for('inicio'))
        
    #Caso donde es peticion GET
    elif request.method == 'GET':
        #Obtenemos las categorias actuales del producto
        form.categorias.data= [c.id for c in producto.categorias]
        #Pre-completamos el form con los datos existentes del producto
        form.nombre.data = producto.nombre
        form.marca.data = producto.marca
        form.descripcion.data = producto.descripcion
        form.precio.data = producto.precio
        form.stock.data = producto.stock

    #Mostramos el form
    return render_template('editar_producto.html', form=form, producto=producto)

# /// Eliminar Producto /// #
@app.route('/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    #Buscamos el producto a eliminar
    producto_a_eliminar= Producto.query.get_or_404(id)

    #Eliminar la imagen del producto a eliminar
    if producto_a_eliminar.imagen_url:
        image_path= os.path.join(app.config['UPLOAD_FOLDER'], producto_a_eliminar.imagen_url)
        #Si existe el path
        if os.path.exists(image_path):
            os.remove(image_path)

    #Lo marcamos para eliminar de la DB
    db.session.delete(producto_a_eliminar)
    #Lo eliminamos
    db.session.commit()
    flash(f'Categoria "{producto_a_eliminar.nombre}" eliminada con exito.', 'success')

    return redirect(url_for('inicio'))

# --- /// Gestion de Categorias /// --- #


# /// Categorias /// #
@app.route('/categorias', methods=['GET', 'POST'])
def gestionar_categorias():
    #Creamos el form de categorias
    form= CategoriaForm()

    #Cuando rellenamos el form
    if form.validate_on_submit():
        nombre_categoria= form.nombre.data.strip() #Ponemos el strip por si hay espacios mal puestos

        #checkeamos si la categoria ya existe
        existing_cat= Categoria.query.filter(db.func.lower(Categoria.nombre) == db.func.lower(nombre_categoria)).first()

        #Si ya existe
        if existing_cat:
            #Avisamos que ya existe
            flash(f'La categoria "{nombre_categoria}" ya existe.', 'warning')
            
        #Si no existe
        else:
            #La agregamos a la DB
            new_categoria= Categoria(nombre=nombre_categoria)
            db.session.add(new_categoria)

            db.session.commit()
            flash(f'La categoria "{new_categoria.nombre} fue agregada con exito.', 'success')

        #Redireccionamos para mostrar la lista de categorias
        return redirect(url_for('gestionar_categorias'))
    
    #Caso donde la solicitud es GET
    #Mostramos todas las categorias existentes
    todas_las_categorias= Categoria.query.order_by(Categoria.nombre).all()
    return render_template('categorias.html', form=form, categorias=todas_las_categorias)

# /// Editar categoria /// #
@app.route('/editar_categoria/<int:id>', methods=['GET', 'POST'])
def editar_categoria(id):
    #Buscamos la categoria a editar
    categoria= Categoria.query.get_or_404(id)
    #Pre-rellenamos los datos con el de la categoria
    form= CategoriaForm(obj=categoria)

    #Caso donde ya estamos llenando el form
    if form.validate_on_submit():
        nuevo_nombre= form.nombre.data.strip()

        #Verificamos si ese nombre ya existe
        existing_categoria= Categoria.query.filter(
            db.func.lower(Categoria.nombre) == db.func.lower(nuevo_nombre), #Buscamos mismo nombre
            Categoria.id != categoria.id #Con distinto ID
        ).first()

        #Si ya hay una categoria con ese nombre
        if existing_categoria:
            #Avisamos que ya existe
            flash(f'La categoria "{nuevo_nombre}" ya existe.', 'warning')
            #Mostramos de nuevo el form para que se cambie
            return render_template('editar_categoria.html', form=form, categoria=categoria)
        
        #Si no existe esa categoria
        else:
            categoria.nombre= nuevo_nombre
            db.session.commit()
            flash(f'La categoria "{categoria.nombre}" fue actualizada con exito.', 'success')
            # Vuelve a la lista de categorías
            return redirect(url_for('gestionar_categorias')) 
        
    #Si es un GET renderizamos el form pre-rellenado
    return render_template('editar_categoria.html', form=form, categoria=categoria)



# /// Eliminar categoria /// #
@app.route('/eliminar_categoria/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    #Buscamos la categoria que queremos eliminar
    categoria_a_eliminar= Categoria.query.get_or_404(id)
    
    #Verificamos que no tenga productos asociados
    #Caso donde tiene productos vinculados
    if categoria_a_eliminar.productos.count() > 0:
        #Avisamos que no se pudo desvincular y cuantos productos tiene asociados
        flash(f'No se puede eliminar la categoria "{categoria_a_eliminar.nombre}" porque tiene {categoria_a_eliminar.productos.count()} producto(s) asociados. Desvincula los productos primero', 'danger')

    #Caso donde no tiene productos vinculados
    else:
        db.session.delete(categoria_a_eliminar)
        db.session.commit()
        flash(f'Categoria "{categoria_a_eliminar.nombre}" eliminada con exito.', 'success')
    
    #Volvemos a gestionar categorias
    return redirect(url_for('gestionar_categorias'))

# --- Punto de Entrada de la Aplicación ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Crea las tablas de la base de datos si no existen
    app.run(debug=True) # Inicia el servidor de desarrollo de Flask (reinicia automáticamente al detectar cambios)
