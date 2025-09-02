import bpy
import sys
import argparse

def main():
    """
    Blender Python script to convert a 3D model file to GLB format.
    This script is intended to be called from the command line by a PHP script.
    
    Example:
    blender.exe --background --python blender_convert.py -- --input "path/to/model.fbx" --output "path/to/model.glb"
    """

    # --- Argument Parsing ---
    
    # Blender's Python environment doesn't handle sys.argv in the standard way.
    # We must parse arguments that appear *after* the '--' separator.
    try:
        args_start_index = sys.argv.index('--') + 1
        argv = sys.argv[args_start_index:]
    except ValueError:
        argv = []

    parser = argparse.ArgumentParser(
        description="Converts a 3D model to GLB format using Blender."
    )
    parser.add_argument(
        "--input", 
        dest="input_path", 
        type=str, 
        required=True,
        help="Path to the input model file (e.g., .fbx, .obj)."
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        type=str,
        required=True,
        help="Path for the exported .glb file."
    )

    # Parse the arguments
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        print(f"Error parsing arguments: {e}")
        # Exit with a non-zero code to indicate failure to the calling script
        sys.exit(1)

    print(f"Starting conversion: {args.input_path} -> {args.output_path}")

    # --- Blender Operations ---

    # 1. Reset the scene to a clean state
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. Import the model based on its extension
    input_lower = args.input_path.lower()
    try:
        if input_lower.endswith('.fbx'):
            bpy.ops.import_scene.fbx(filepath=args.input_path)
        elif input_lower.endswith('.obj'):
            bpy.ops.import_scene.obj(filepath=args.input_path)
        # Add other importers as needed (e.g., for .dae, .stl)
        else:
            print(f"Error: Unsupported input file format for '{args.input_path}'")
            sys.exit(1)
        
        print("Import successful.")

    except Exception as e:
        print(f"Blender Error: Failed to import file '{args.input_path}'.")
        print(f"Details: {e}")
        sys.exit(1)

    # 3. Export the scene to GLB format
    try:
        # These settings are good defaults for web/AR applications
        bpy.ops.export_scene.gltf(
            filepath=args.output_path,
            export_format='GLB',
            export_apply=True,                          # Apply modifiers
            export_draco_mesh_compression_enable=True,  # Use Draco compression
            export_draco_mesh_compression_level=6,
            export_lights=False,                        # Not usually needed
            export_cameras=False                        # Not usually needed
        )
        print("Export to GLB successful.")

    except Exception as e:
        print(f"Blender Error: Failed to export to GLB file '{args.output_path}'.")
        print(f"Details: {e}")
        sys.exit(1)
        
    print("Conversion completed successfully.")
    # A successful exit has a code of 0
    sys.exit(0)


if __name__ == "__main__":
    main()
