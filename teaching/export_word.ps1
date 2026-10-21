param([Parameter(Mandatory=$true)][string]$DocumentPath)
$ErrorActionPreference='Stop'
$resolved=[IO.Path]::GetFullPath($DocumentPath)
if (-not $resolved.StartsWith('H:\Career_AI_Portfolio\projects\01_recommendation_service\teaching\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected document scope' }
$pdf=[IO.Path]::ChangeExtension($resolved,'.pdf')
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
try {
    $doc=$word.Documents.Open($resolved,$false,$true)
    $doc.Repaginate()
    $doc.ExportAsFixedFormat($pdf,17)
    $pages=$doc.ComputeStatistics(2)
    $doc.Close(0)
    [pscustomobject]@{Document=$resolved;Pdf=$pdf;Pages=$pages}|ConvertTo-Json -Compress
} finally {
    $word.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
