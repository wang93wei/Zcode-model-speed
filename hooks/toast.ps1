param([string]$Payload)
# Native Windows toast notification. Reads title/body from a UTF-8 JSON file
# to avoid encoding issues on the command line. This file is ASCII-only.
$ErrorActionPreference = 'Stop'
try {
    $j = Get-Content -Raw -Encoding UTF8 $Payload | ConvertFrom-Json
    $title = [string]$j.title
    $body = [string]$j.body
    $t = $title.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')
    $b = $body.Replace('&', '&amp;').Replace('<', '&lt;').Replace('>', '&gt;')

    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast duration='short'><visual><binding template='ToastGeneric'><text>$t</text><text>$b</text></binding></visual></toast>")
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
} catch {
    # Notification is best-effort; never fail the hook.
}
exit 0
