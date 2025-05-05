import aspose.words as aw

doc = aw.Document()
builder = aw.DocumentBuilder(doc)

shape = builder.insert_image("inputt.jpg")
shape.get_shape_renderer().save("Output.svg", aw.saving.ImageSaveOptions(aw.SaveFormat.SVG))