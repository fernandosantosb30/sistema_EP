# providers/forms.py
from django import forms
from .models import (
    Provedor, Contato, CidadeAtendida, PrestadorServico,
    CidadeAtendidaPrestador,
)

class ProvedorForm(forms.ModelForm):
    class Meta:
        model = Provedor
        fields = [
            'nome', 'ativo', 'razao_social', 'cnpj', 
            'parceiro_bst', 'fibra', 'radio', 
            'link_dedicado', 'link_banda_larga', 'zona_rural'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Adicione os novos para o visual do card
            'fibra': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'radio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_dedicado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_banda_larga': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'zona_rural': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parceiro_bst': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ['nome', 'cargo', 'telefone', 'email',] # Inclua aqui
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white'}),
             # Adicione o widget
        }
        
class UfValidaMixin:
    def clean_nome(self):
        from .utils import normalizar_texto
        return normalizar_texto(self.cleaned_data['nome'])

    def clean_uf(self):
        from .services.consultas import validar_uf
        try:
            return validar_uf(self.cleaned_data['uf'])
        except ValueError as exc:
            raise forms.ValidationError(str(exc))


class CidadeForm(UfValidaMixin, forms.ModelForm):
    class Meta:
        model = CidadeAtendida
        fields = ['nome', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'uf': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
        }


class PrestadorServicoForm(forms.ModelForm):
    DOCUMENTACAO_CHOICES = ((True, 'Sim'), (False, 'Não'))

    possui_documentacao = forms.TypedChoiceField(
        label='Possui documentação?',
        choices=DOCUMENTACAO_CHOICES,
        coerce=lambda value: value == 'True',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = PrestadorServico
        fields = [
            'razao_social', 'nome_fantasia', 'cnpj', 'contato', 'telefone', 'email',
            'instalacao_satelite', 'teste_rede', 'possui_documentacao', 'observacoes',
        ]
        widgets = {
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'contato': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'instalacao_satelite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'teste_rede': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean_cnpj(self):
        # Mantém o campo opcional compatível com a restrição unique do banco.
        return self.cleaned_data['cnpj'] or None


class CidadeAtendidaPrestadorForm(UfValidaMixin, forms.ModelForm):
    class Meta:
        model = CidadeAtendidaPrestador
        fields = ['nome', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade'}),
            'uf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'UF', 'maxlength': 2}),
        }


from django.contrib.auth.forms import SetPasswordForm


class UsuarioEdicaoForm(SetPasswordForm):
    autoridade = forms.ChoiceField(
        label='Autoridade',
        choices=[('usuario', 'Usuário comum'), ('admin', 'Administrador (acesso total)')],
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['new_password1'].required = False
        self.fields['new_password2'].required = False
        self.fields['new_password1'].help_text = 'Deixe os dois campos de senha vazios para manter a senha atual.'
        self.fields['autoridade'].initial = 'admin' if user.is_superuser else 'usuario'

    def clean(self):
        cleaned = super().clean()
        if bool(cleaned.get('new_password1')) != bool(cleaned.get('new_password2')):
            raise forms.ValidationError('Preencha e confirme a nova senha nos dois campos.')
        return cleaned

    def save(self, commit=True):
        if self.cleaned_data.get('new_password1'):
            super().save(commit=False)
        self.user.is_superuser = self.cleaned_data['autoridade'] == 'admin'
        self.user.is_staff = self.user.is_superuser
        if commit:
            self.user.save()
        return self.user
