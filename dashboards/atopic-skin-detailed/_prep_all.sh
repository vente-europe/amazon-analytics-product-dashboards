set -e
for b in "DE Check" "DE Oil" "DE Wash" "FR Cream" "FR Oil" "FR Wash" "IT Cream" "IT Oil" "IT Wash" "ES Cream" "ES Oil" "ES Wash"; do
  echo "=== prep $b ==="
  python voc_pipeline.py prep $b
done
echo "ALL PREP DONE"
