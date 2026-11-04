set -e
python3 /root/create_packet.py
render_dir=/root/tmp/docs/render_packet_20261103_v2
mkdir -p "$render_dir"
soffice -env:UserInstallation=file:///tmp/lo_packet_profile_20261103_v2 --headless --convert-to pdf --outdir "$render_dir" /root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx
pdfinfo "$render_dir/docops_v2_l3_001_docx_controlled_document_release_repair_output.pdf" | sed -n '1,25p'
pdftoppm -png -r 150 "$render_dir/docops_v2_l3_001_docx_controlled_document_release_repair_output.pdf" "$render_dir/page"
find "$render_dir" -maxdepth 1 -type f -printf '%f %s bytes\n' | sort