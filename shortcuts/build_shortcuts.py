"""Build the two iOS Shortcuts as unsigned .wflow plists.

Sign them on a Mac:  shortcuts sign --mode anyone --input X.unsigned.shortcut --output X.shortcut
Usage: python3 build_shortcuts.py OUTDIR [WEBHOOK_URL]
Without WEBHOOK_URL the Save Recipe shortcut asks for it on import.
"""
import plistlib, sys, uuid

OUT = sys.argv[1]
WEBHOOK = sys.argv[2] if len(sys.argv) > 2 else ""
OBJ = "￼"


def uid():
    return str(uuid.uuid4()).upper()


def act(ident, **params):
    params.setdefault("UUID", uid())
    return {"WFWorkflowActionIdentifier": "is.workflow.actions." + ident, "WFWorkflowActionParameters": params}


def out_ref(action, name):
    return {"OutputUUID": action["WFWorkflowActionParameters"]["UUID"], "Type": "ActionOutput", "OutputName": name}


def token_attachment(ref):
    return {"Value": ref, "WFSerializationType": "WFTextTokenAttachment"}


def token_string(text, refs=None):
    """text with OBJ placeholders replaced in order by refs."""
    value = {"string": text}
    if refs:
        ranges, pos, i = {}, -1, 0
        for ref in refs:
            pos = text.index(OBJ, pos + 1)
            ranges[f"{{{pos}, 1}}"] = ref
        value["attachmentsByRange"] = ranges
    return {"Value": value, "WFSerializationType": "WFTextTokenString"}


INPUT = {"Type": "ExtensionInput"}


def dict_field(items):
    return {
        "Value": {"WFDictionaryFieldValueItems": [
            {"WFItemType": 0, "WFKey": token_string(k), "WFValue": v} for k, v in items
        ]},
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def conditional(group, mode, **extra):
    return act("conditional", GroupingIdentifier=group, WFControlFlowMode=mode, **extra)


def notify_from(download, title_fallback):
    msg = act("getvalueforkey", WFInput=token_attachment(out_ref(download, "Contents of URL")),
              WFDictionaryKey="message")
    note = act("notification", WFNotificationActionTitle="Recipes",
               WFNotificationActionBody=token_string(OBJ, [out_ref(msg, "Dictionary Value")]),
               WFNotificationActionSound=False)
    return [msg, note]


def post(url_text_action, body_type, **body):
    return act("downloadurl",
               WFURL=token_string(OBJ, [out_ref(url_text_action, "Text")]),
               WFHTTPMethod="POST", WFHTTPBodyType=body_type, ShowHeaders=False, **body)


def save_recipe():
    hook = act("gettext", WFTextActionText=WEBHOOK or "https://YOUR-HA/api/webhook/ID")
    links = act("detect.link", WFInput=token_attachment(INPUT))
    g1 = uid()
    first = act("getitemfromlist", WFInput=token_attachment(out_ref(links, "URLs")), WFItemSpecifier="First Item")
    dl_url = post(hook, "JSON", WFJSONValues=dict_field([("url", token_string(OBJ, [out_ref(first, "Item from List")]))]))
    kind = act("getitemtype", WFInput=token_attachment(INPUT))
    g2 = uid()
    text_in = act("detect.text", WFInput=token_attachment(INPUT))
    dl_text = post(hook, "JSON", WFJSONValues=dict_field([("text", token_string(OBJ, [out_ref(text_in, "Text")]))]))
    g3 = uid()
    jpeg = act("image.convert", WFInput=token_attachment(INPUT), WFImageFormat="JPEG",
               WFImageCompressionQuality=0.85, WFImagePreserveMetadata=False)
    dl_img = post(hook, "File", WFRequestVariable=token_attachment(out_ref(jpeg, "Converted Image")))
    dl_file = post(hook, "File", WFRequestVariable=token_attachment(INPUT))
    actions = [
        act("comment", WFCommentActionText="Sends the shared link, photo, PDF or text to Home Assistant (Recipes). Everything else happens in Home Assistant."),
        hook,
        links,
        conditional(g1, 0, WFInput={"Type": "Variable", "Variable": token_attachment(out_ref(links, "URLs"))}, WFCondition=100),
        first, dl_url, *notify_from(dl_url, "Saved"),
        conditional(g1, 1),
        kind,
        conditional(g2, 0, WFInput={"Type": "Variable", "Variable": token_attachment(out_ref(kind, "Type"))},
                    WFCondition=4, WFConditionalActionString="Text"),
        text_in, dl_text, *notify_from(dl_text, "Saved"),
        conditional(g2, 1),
        conditional(g3, 0, WFInput={"Type": "Variable", "Variable": token_attachment(out_ref(kind, "Type"))},
                    WFCondition=4, WFConditionalActionString="Image"),
        jpeg, dl_img, *notify_from(dl_img, "Saved"),
        conditional(g3, 1),
        dl_file, *notify_from(dl_file, "Saved"),
        conditional(g3, 2),
        conditional(g2, 2),
        conditional(g1, 2),
    ]
    questions = []
    if not WEBHOOK:
        questions.append({
            "ActionIndex": 1, "Category": "Parameter", "ParameterKey": "WFTextActionText",
            "Text": "Paste your Recipes webhook URL (Recipes app → ••• → Copy webhook URL)",
            "DefaultValue": "",
        })
    return wrap(actions, ["WFURLContentItem", "WFImageContentItem", "WFPDFContentItem", "WFStringContentItem",
                          "WFRichTextContentItem", "WFSafariWebPageContentItem", "WFGenericFileContentItem"],
                types=["ActionExtension", "WFWorkflowTypeShowInSearch"], icon=(4282601983, 59842), questions=questions,
                no_input="WFWorkflowNoInputBehaviorGetClipboard")


def recipe_timer():
    num = act("detect.number", WFInput=token_attachment(INPUT))
    start = act("timer.start", WFDuration={
        "Value": {"Magnitude": token_attachment(out_ref(num, "Numbers")), "Unit": "sec"},
        "WFSerializationType": "WFQuantityFieldValue"})
    actions = [
        act("comment", WFCommentActionText="Started by the Recipes app: input is the timer length in seconds."),
        num, start,
    ]
    return wrap(actions, ["WFStringContentItem", "WFNumberContentItem"], types=["WFWorkflowTypeShowInSearch"],
                icon=(4294223938, 61440), questions=[], no_input=None)


def wrap(actions, classes, types, icon, questions, no_input):
    wf = {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "4711",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": icon[0], "WFWorkflowIconGlyphNumber": icon[1]},
        "WFWorkflowImportQuestions": questions,
        "WFWorkflowInputContentItemClasses": classes,
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": types,
        "WFQuickActionSurfaces": [],
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": True,
    }
    if no_input:
        wf["WFWorkflowNoInputBehavior"] = {"Name": no_input, "Parameters": {}}
    return wf


for name, wf in (("Save Recipe", save_recipe()), ("Recipe Timer", recipe_timer())):
    with open(f"{OUT}/{name}.unsigned.shortcut", "wb") as f:
        plistlib.dump(wf, f, fmt=plistlib.FMT_BINARY)
    print("built", name, len(wf["WFWorkflowActions"]), "actions")
