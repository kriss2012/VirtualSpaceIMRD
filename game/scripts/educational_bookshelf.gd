extends Node3D

# Procedural BCA / MCA educational bookshelf for Godot 4.x
# Attach this script to a Node3D root and run the scene.
#
# Layout
#   Left bay  : BCA  - Semester 1 (top) ... Semester 6 (bottom)
#   Right bay : MCA  - Semester 1-4, then two "Reference" shelves
#
# Every book has a readable spine (title + author), a cover colour by subject
# category, thickness by "weight" of the book, and metadata you can query:
#   book.get_meta("title"), "author", "category", "program", "shelf"
#
# Edit _build_catalog() to match your own university syllabus.

@export var shelf_width: float = 9.0
@export var shelf_height: float = 9.0
@export var shelf_depth: float = 1.0

@export var generate_on_start: bool = true
@export var random_seed: int = 42
@export var add_camera_and_lights: bool = true
@export var show_spine_text: bool = true

const FRAME := 0.18      # outer frame thickness
const BOARD := 0.12      # shelf board thickness
const DIVIDER := 0.10    # vertical divider thickness
const BACK := 0.06       # back panel thickness
const FONT_PX := 48

# Cover colours per subject category.
const CATEGORY_COLORS := {
    "prog":   Color(0.12, 0.25, 0.46),   # programming languages
    "db":     Color(0.10, 0.35, 0.25),   # databases
    "net":    Color(0.70, 0.35, 0.12),   # networking
    "math":   Color(0.32, 0.22, 0.46),   # mathematics
    "ai":     Color(0.55, 0.10, 0.13),   # AI / ML / data mining
    "se":     Color(0.12, 0.40, 0.45),   # software engineering
    "sys":    Color(0.20, 0.22, 0.27),   # computer organisation / OS
    "sec":    Color(0.26, 0.08, 0.10),   # security
    "alg":    Color(0.62, 0.46, 0.14),   # algorithms / theory
    "gfx":    Color(0.55, 0.22, 0.40),   # graphics
    "mgmt":   Color(0.55, 0.45, 0.30),   # management / business
    "cloud":  Color(0.25, 0.45, 0.62),   # cloud / big data
    "web":    Color(0.35, 0.40, 0.18),   # web technologies
}

var rng := RandomNumberGenerator.new()
var wood: StandardMaterial3D
var dark_wood: StandardMaterial3D
var gold: StandardMaterial3D
var material_cache: Dictionary = {}
var catalog: Array = []
var rows: int = 0
var columns: int = 0


func _ready() -> void:
    if generate_on_start:
        generate_bookshelf()


func generate_bookshelf() -> void:
    # Remove previously generated objects immediately so names never clash.
    for child in get_children():
        remove_child(child)
        child.queue_free()

    rng.seed = random_seed
    material_cache.clear()

    catalog = _build_catalog()
    columns = catalog.size()
    rows = 0
    for program in catalog:
        rows = maxi(rows, program["shelves"].size())

    create_materials()
    create_frame()
    create_shelf_boards()
    create_vertical_dividers()
    create_headers_and_labels()
    create_books()

    if add_camera_and_lights:
        create_environment()

    print("Bookshelf generated: %d programs, %d shelves, %d books." % [
        columns, rows, count_books()
    ])


# ---------------------------------------------------------------------------
# Catalogue (edit this to match your syllabus)
# ---------------------------------------------------------------------------

func _b(title: String, author: String, cat: String, thick: float = 1.0) -> Dictionary:
    return {"title": title, "author": author, "cat": cat, "thick": thick}


func _build_catalog() -> Array:
    var bca := {
        "code": "BCA",
        "name": "Bachelor of Computer Applications",
        "shelves": [
            {"label": "BCA  SEM 1", "books": [
                _b("Computer Fundamentals", "P. K. Sinha", "sys", 1.2),
                _b("Fundamentals of Computers", "V. Rajaraman", "sys"),
                _b("Let Us C", "Y. Kanetkar", "prog"),
                _b("Programming in ANSI C", "Balagurusamy", "prog", 1.2),
                _b("Digital Design", "M. Morris Mano", "sys", 1.1),
                _b("Discrete Mathematics", "K. Rosen", "math", 1.6),
            ]},
            {"label": "BCA  SEM 2", "books": [
                _b("Data Structures Using C", "R. Thareja", "alg", 1.2),
                _b("Fundamentals of Data Structures", "Horowitz, Sahni", "alg", 1.2),
                _b("Computer System Architecture", "M. Morris Mano", "sys", 1.2),
                _b("OOP with C++", "Balagurusamy", "prog", 1.1),
                _b("Operating System Concepts", "Silberschatz", "sys", 1.8),
            ]},
            {"label": "BCA  SEM 3", "books": [
                _b("Database System Concepts", "Silberschatz", "db", 1.8),
                _b("Fundamentals of Database Systems", "Elmasri, Navathe", "db", 1.6),
                _b("Java: The Complete Reference", "H. Schildt", "prog", 1.6),
                _b("Computer Networks", "Tanenbaum", "net", 1.5),
                _b("Software Engineering", "Pressman", "se", 1.7),
                _b("Design and Analysis of Algorithms", "Levitin", "alg", 1.3),
            ]},
            {"label": "BCA  SEM 4", "books": [
                _b("Programming with Java", "Balagurusamy", "prog", 1.2),
                _b("Python Programming", "R. Thareja", "prog", 1.1),
                _b("Data Communications and Networking", "Forouzan", "net", 1.6),
                _b("Software Engineering", "Sommerville", "se", 1.5),
                _b("HTML5 Black Book", "Kogent Learning", "web", 1.5),
                _b("Modern Operating Systems", "Tanenbaum", "sys", 1.6),
            ]},
            {"label": "BCA  SEM 5", "books": [
                _b("PHP and MySQL Web Development", "Welling, Thomson", "web", 1.4),
                _b("Computer Graphics", "Hearn, Baker", "gfx", 1.3),
                _b("Artificial Intelligence", "Rich, Knight", "ai", 1.4),
                _b("Intro to Automata Theory", "Hopcroft, Ullman", "alg", 1.5),
                _b("Cryptography and Network Security", "Forouzan", "sec", 1.4),
                _b("Management Information Systems", "Laudon", "mgmt", 1.4),
            ]},
            {"label": "BCA  SEM 6", "books": [
                _b("Data Mining: Concepts and Techniques", "Han, Kamber", "ai", 1.7),
                _b("Machine Learning", "T. Mitchell", "ai", 1.3),
                _b("Mastering Cloud Computing", "R. Buyya", "cloud", 1.3),
                _b("Software Testing", "N. Chauhan", "se", 1.3),
                _b("E-Commerce", "Laudon, Traver", "mgmt", 1.4),
            ]},
        ]
    }

    var mca := {
        "code": "MCA",
        "name": "Master of Computer Applications",
        "shelves": [
            {"label": "MCA  SEM 1", "books": [
                _b("Introduction to Algorithms", "Cormen et al.", "alg", 1.9),
                _b("Computer Organization and Architecture", "Stallings", "sys", 1.6),
                _b("Discrete Mathematical Structures", "Kolman", "math", 1.3),
                _b("Data Structures and Algorithms in Java", "Goodrich", "alg", 1.5),
                _b("Operating System Concepts", "Silberschatz", "sys", 1.8),
                _b("Database System Concepts", "Silberschatz", "db", 1.8),
            ]},
            {"label": "MCA  SEM 2", "books": [
                _b("Computer Networks", "Tanenbaum", "net", 1.5),
                _b("Software Engineering", "Pressman", "se", 1.7),
                _b("Java: The Complete Reference", "H. Schildt", "prog", 1.6),
                _b("Design and Analysis of Computer Algorithms", "Aho et al.", "alg", 1.3),
                _b("Fundamentals of Database Systems", "Elmasri, Navathe", "db", 1.6),
                _b("Operating Systems: Internals", "Stallings", "sys", 1.8),
            ]},
            {"label": "MCA  SEM 3", "books": [
                _b("Theory of Computation", "M. Sipser", "alg", 1.3),
                _b("Artificial Intelligence: A Modern Approach", "Russell, Norvig", "ai", 1.9),
                _b("Compilers: Principles, Techniques", "Aho et al.", "alg", 1.7),
                _b("Cryptography and Network Security", "Stallings", "sec", 1.6),
                _b("Mastering Cloud Computing", "R. Buyya", "cloud", 1.3),
                _b("Web Technologies", "Uttam K. Roy", "web", 1.3),
            ]},
            {"label": "MCA  SEM 4", "books": [
                _b("Machine Learning", "T. Mitchell", "ai", 1.3),
                _b("Data Mining: Concepts and Techniques", "Han, Kamber", "ai", 1.7),
                _b("Deep Learning", "Goodfellow et al.", "ai", 1.7),
                _b("Hadoop: The Definitive Guide", "T. White", "cloud", 1.6),
                _b("Software Project Management", "Hughes, Cotterell", "mgmt", 1.4),
                _b("Distributed Systems", "Tanenbaum, van Steen", "sys", 1.5),
            ]},
            {"label": "MCA  REFERENCE I", "books": [
                _b("Clean Code", "R. C. Martin", "se", 1.2),
                _b("Design Patterns", "Gamma et al.", "se", 1.2),
                _b("The Pragmatic Programmer", "Hunt, Thomas", "se", 1.2),
                _b("Python for Data Analysis", "W. McKinney", "prog", 1.3),
                _b("Effective Java", "J. Bloch", "prog", 1.2),
                _b("Code Complete", "S. McConnell", "se", 1.8),
            ]},
            {"label": "MCA  REFERENCE II", "books": [
                _b("Computer Networking: Top-Down", "Kurose, Ross", "net", 1.7),
                _b("Modern Operating Systems", "Tanenbaum", "sys", 1.6),
                _b("Computer Architecture", "Hennessy, Patterson", "sys", 1.8),
                _b("Computer Organization and Design", "Patterson, Hennessy", "sys", 1.7),
                _b("The Linux Command Line", "W. Shotts", "sys", 1.2),
            ]},
        ]
    }

    return [bca, mca]


# ---------------------------------------------------------------------------
# Materials and primitives
# ---------------------------------------------------------------------------

func make_material(color: Color, roughness: float = 0.8) -> StandardMaterial3D:
    var key := "%s_%s" % [color.to_html(), str(roughness)]
    if material_cache.has(key):
        return material_cache[key]

    var material := StandardMaterial3D.new()
    material.albedo_color = color
    material.roughness = roughness
    material_cache[key] = material
    return material


func create_materials() -> void:
    wood = make_material(Color(0.48, 0.29, 0.14), 0.75)
    dark_wood = make_material(Color(0.23, 0.12, 0.055), 0.85)
    gold = make_material(Color(0.80, 0.66, 0.39), 0.45)
    gold.metallic = 0.6


func create_box(
        object_name: String,
        size: Vector3,
        position: Vector3,
        material: Material,
        parent: Node3D = self
    ) -> MeshInstance3D:

    var mesh_instance := MeshInstance3D.new()
    mesh_instance.name = object_name

    var box := BoxMesh.new()
    box.size = size

    mesh_instance.mesh = box
    mesh_instance.position = position
    mesh_instance.material_override = material

    parent.add_child(mesh_instance)
    return mesh_instance


# Creates a Label3D whose pixel size is computed so the text fits inside
# max_len x max_thick (measured in the label's own, un-rotated frame).
func add_fitted_label(
        parent: Node3D,
        text: String,
        position: Vector3,
        max_len: float,
        max_thick: float,
        color: Color,
        align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_CENTER,
        rotation_z: float = 0.0
    ) -> Label3D:

    var font := ThemeDB.fallback_font
    var lines := text.split("\n")

    var longest := 1.0
    for line in lines:
        longest = maxf(
            longest,
            font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_PX).x
        )

    var text_height := font.get_height(FONT_PX) * float(lines.size())
    var pixel := minf(max_len / longest, max_thick / text_height)
    pixel = minf(pixel, 0.01)

    var label := Label3D.new()
    label.text = text
    label.font_size = FONT_PX
    label.pixel_size = pixel
    label.modulate = color
    label.outline_size = 0
    label.shaded = false
    label.double_sided = false
    label.alpha_cut = Label3D.ALPHA_CUT_DISCARD
    label.horizontal_alignment = align
    label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
    label.position = position
    label.rotation.z = rotation_z

    parent.add_child(label)
    return label


# ---------------------------------------------------------------------------
# Cabinet geometry
# ---------------------------------------------------------------------------

func inner_height() -> float:
    return shelf_height - 2.0 * FRAME


func row_height() -> float:
    return (inner_height() - float(rows - 1) * BOARD) / float(rows)


# Y of the top surface of the board that row `i` (0 = top row) sits on.
func row_bottom(i: int) -> float:
    return FRAME + float(rows - 1 - i) * (row_height() + BOARD)


func bay_width() -> float:
    var inner := shelf_width - 2.0 * FRAME
    return (inner - float(columns - 1) * DIVIDER) / float(columns)


func bay_left(column_index: int) -> float:
    return -shelf_width / 2.0 + FRAME + float(column_index) * (bay_width() + DIVIDER)


func create_frame() -> void:
    # Back panel.
    create_box(
        "Back_Panel",
        Vector3(shelf_width, shelf_height, BACK),
        Vector3(0, shelf_height / 2.0, -shelf_depth / 2.0 + BACK / 2.0),
        dark_wood
    )

    create_box(
        "Left_Side",
        Vector3(FRAME, shelf_height, shelf_depth),
        Vector3(-shelf_width / 2.0 + FRAME / 2.0, shelf_height / 2.0, 0),
        wood
    )

    create_box(
        "Right_Side",
        Vector3(FRAME, shelf_height, shelf_depth),
        Vector3(shelf_width / 2.0 - FRAME / 2.0, shelf_height / 2.0, 0),
        wood
    )

    create_box(
        "Top_Board",
        Vector3(shelf_width, FRAME, shelf_depth),
        Vector3(0, shelf_height - FRAME / 2.0, 0),
        wood
    )

    create_box(
        "Bottom_Board",
        Vector3(shelf_width, FRAME, shelf_depth),
        Vector3(0, FRAME / 2.0, 0),
        wood
    )


func create_shelf_boards() -> void:
    var depth := shelf_depth - BACK
    for i in range(rows - 1):
        create_box(
            "Shelf_%d" % (i + 1),
            Vector3(shelf_width - 2.0 * FRAME, BOARD, depth),
            Vector3(0, row_bottom(i) - BOARD / 2.0, BACK / 2.0),
            wood
        )


func create_vertical_dividers() -> void:
    var depth := shelf_depth - BACK
    for column_index in range(1, columns):
        var x := bay_left(column_index) - DIVIDER / 2.0
        create_box(
            "Divider_%d" % column_index,
            Vector3(DIVIDER, inner_height(), depth),
            Vector3(x, shelf_height / 2.0, BACK / 2.0),
            wood
        )


# ---------------------------------------------------------------------------
# Signage: program headers on the top board, semester labels on shelf edges
# ---------------------------------------------------------------------------

func create_headers_and_labels() -> void:
    var cream := Color(0.96, 0.90, 0.76)
    var front_z := shelf_depth / 2.0 + 0.002

    for column_index in range(columns):
        var program: Dictionary = catalog[column_index]
        var center_x := bay_left(column_index) + bay_width() / 2.0

        var header := add_fitted_label(
            self,
            "%s  -  %s" % [program["code"], program["name"]],
            Vector3(center_x, shelf_height - FRAME / 2.0, front_z),
            bay_width() * 0.92,
            FRAME * 0.55,
            cream
        )
        header.name = "Header_%s" % program["code"]

        var shelves: Array = program["shelves"]
        for i in range(shelves.size()):
            var board_y := row_bottom(i) - BOARD / 2.0
            var thickness := BOARD
            if i == rows - 1:
                board_y = FRAME / 2.0
                thickness = FRAME

            var tag := add_fitted_label(
                self,
                shelves[i]["label"],
                Vector3(bay_left(column_index) + 0.10, board_y, front_z),
                bay_width() * 0.6,
                thickness * 0.55,
                cream,
                HORIZONTAL_ALIGNMENT_LEFT
            )
            tag.name = "Label_%s_%d" % [program["code"], i + 1]


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

func wrap_title(title: String, max_chars: int = 18) -> Array:
    var lines: Array = []
    var current := ""
    for word in title.split(" "):
        if current == "":
            current = word
        elif current.length() + 1 + word.length() <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current != "":
        lines.append(current)
    return lines


func create_books() -> void:
    for column_index in range(columns):
        var program: Dictionary = catalog[column_index]
        var shelves: Array = program["shelves"]
        for i in range(shelves.size()):
            fill_shelf(program, shelves[i], column_index, i)


func fill_shelf(program: Dictionary, shelf: Dictionary, column_index: int, row_index: int) -> void:
    var books: Array = shelf["books"]
    var left := bay_left(column_index)
    var usable := bay_width() - 0.30       # leave room for a bookend
    var row_h := row_height()
    var gap := 0.012

    # First pass: raw widths, then scale down if the shelf would overflow.
    var widths: Array = []
    var total := 0.0
    for book_data in books:
        var w: float = (0.30 + 0.12 * float(book_data["thick"])) * rng.randf_range(0.94, 1.06)
        widths.append(w)
        total += w + gap
    var scale := minf(1.0, usable / total)

    var x := left + 0.08
    var front_z := shelf_depth / 2.0 - 0.02

    for index in range(books.size()):
        var data: Dictionary = books[index]
        var width: float = widths[index] * scale

        var height: float = clampf(
            row_h * (0.70 + 0.06 * float(data["thick"])) * rng.randf_range(0.96, 1.04),
            0.5,
            row_h - 0.08
        )
        var depth: float = shelf_depth * rng.randf_range(0.52, 0.62)

        var base_color: Color = CATEGORY_COLORS.get(data["cat"], Color(0.3, 0.3, 0.3))
        var cover := Color(
            clampf(base_color.r + rng.randf_range(-0.04, 0.04), 0.0, 1.0),
            clampf(base_color.g + rng.randf_range(-0.04, 0.04), 0.0, 1.0),
            clampf(base_color.b + rng.randf_range(-0.04, 0.04), 0.0, 1.0)
        )

        var book := create_box(
            "Book_%s_R%d_B%d" % [program["code"], row_index, index],
            Vector3(width, height, depth),
            Vector3(
                x + width / 2.0,
                row_bottom(row_index) + height / 2.0,
                front_z - depth / 2.0 - rng.randf_range(0.0, 0.03)
            ),
            make_material(cover, 0.9)
        )
        book.rotation.z = deg_to_rad(rng.randf_range(-1.0, 1.0))

        book.set_meta("title", data["title"])
        book.set_meta("author", data["author"])
        book.set_meta("category", data["cat"])
        book.set_meta("program", program["code"])
        book.set_meta("shelf", shelf["label"])

        decorate_spine(book, data, width, height, depth, cover)

        x += width + gap

    # Bookend closing the group.
    var end_h := row_h * 0.45
    create_box(
        "Bookend_%s_R%d" % [program["code"], row_index],
        Vector3(0.07, end_h, shelf_depth * 0.5),
        Vector3(
            x + 0.04,
            row_bottom(row_index) + end_h / 2.0,
            front_z - shelf_depth * 0.25
        ),
        dark_wood
    )


func decorate_spine(
        book: MeshInstance3D,
        data: Dictionary,
        width: float,
        height: float,
        depth: float,
        cover: Color
    ) -> void:

    var spine_z := depth / 2.0

    # Gold bands near the head and tail of the spine.
    for sign in [1.0, -1.0]:
        create_box(
            "Band",
            Vector3(width * 0.98, 0.03, 0.006),
            Vector3(0, height * 0.43 * sign, spine_z + 0.001),
            gold,
            book
        )

    if not show_spine_text:
        return

    var lines := wrap_title(data["title"])
    lines.append(data["author"])

    var text_color := Color(0.97, 0.93, 0.82)
    if cover.get_luminance() > 0.45:
        text_color = Color(0.10, 0.08, 0.06)

    # Rotated -90 degrees so the text reads top-to-bottom like a real spine.
    add_fitted_label(
        book,
        "\n".join(PackedStringArray(lines)),
        Vector3(0, 0, spine_z + 0.004),
        height * 0.72,
        width * 0.80,
        text_color,
        HORIZONTAL_ALIGNMENT_CENTER,
        -PI / 2.0
    )


func count_books() -> int:
    var count := 0
    for program in catalog:
        for shelf in program["shelves"]:
            count += shelf["books"].size()
    return count


# ---------------------------------------------------------------------------
# Camera, lights, floor
# ---------------------------------------------------------------------------

func create_environment() -> void:
    var env := Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color(0.10, 0.10, 0.12)
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color(0.85, 0.80, 0.72)
    env.ambient_light_energy = 0.6

    var world_env := WorldEnvironment.new()
    world_env.name = "WorldEnvironment"
    world_env.environment = env
    add_child(world_env)

    var sun := DirectionalLight3D.new()
    sun.name = "Sun"
    sun.rotation_degrees = Vector3(-30, 20, 0)
    sun.light_energy = 1.0
    sun.shadow_enabled = true
    add_child(sun)

    var fill := OmniLight3D.new()
    fill.name = "FillLight"
    fill.position = Vector3(0, shelf_height * 0.6, shelf_depth * 6.0)
    fill.omni_range = 40.0
    fill.light_energy = 1.2
    add_child(fill)

    var floor_mesh := MeshInstance3D.new()
    floor_mesh.name = "Floor"
    var plane := PlaneMesh.new()
    plane.size = Vector2(40, 40)
    floor_mesh.mesh = plane
    floor_mesh.position = Vector3(0, -0.005, 0)
    floor_mesh.material_override = make_material(Color(0.30, 0.27, 0.24), 0.95)
    add_child(floor_mesh)

    var camera := Camera3D.new()
    camera.name = "Camera"
    camera.fov = 45.0
    camera.position = Vector3(0, shelf_height * 0.5, maxf(shelf_height, shelf_width) * 1.6)
    add_child(camera)
    camera.look_at(Vector3(0, shelf_height * 0.5, 0))
    camera.current = true
